import { Injectable } from '@angular/core';
import { createClient, SupabaseClient } from '@supabase/supabase-js';

export interface DashboardMetrics {
  proyectos: number;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  avgTokensPerProject: number;
  estimatedCost: number;
}

export interface StorageFileItem {
  name: string;
  bucket: string;
  folder: string;
  path: string;
  size: number;
  type: string;
  url: string;
  estimatedCompressedSize?: number;
  compressionRatio?: number;
}

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private supabase: SupabaseClient | null = null;
  private currentSupabaseUrl = '';
  private currentSupabaseKey = '';
  private readonly backendBaseUrl = 'http://localhost:8000';

  setConnection(url: string, key: string): void {
    const supabaseUrl = url.trim();
    const supabaseKey = key.trim();

    if (!supabaseUrl || !supabaseKey) {
      throw new Error('Falta la URL o la anon key de Supabase');
    }

    if (this.supabase && this.currentSupabaseUrl === supabaseUrl && this.currentSupabaseKey === supabaseKey) {
      return;
    }

    this.currentSupabaseUrl = supabaseUrl;
    this.currentSupabaseKey = supabaseKey;
    this.supabase = createClient(supabaseUrl, supabaseKey);
  }

  async getMetrics(): Promise<DashboardMetrics> {
    if (!this.supabase) {
      throw new Error('No hay conexión activa a Supabase');
    }

    const { data, error } = await this.supabase
      .from('disenos_racks')
      .select('input_tokens, output_tokens')
      .order('created_at', { ascending: false });

    if (error) {
      throw error;
    }

    const rows = data ?? [];
    const inputTokens = rows.reduce((sum, row) => sum + Number((row as { input_tokens?: number }).input_tokens ?? 0), 0);
    const outputTokens = rows.reduce((sum, row) => sum + Number((row as { output_tokens?: number }).output_tokens ?? 0), 0);
    const totalTokens = inputTokens + outputTokens;
    const avgTokensPerProject = rows.length > 0 ? totalTokens / rows.length : 0;
    const estimatedCost = totalTokens / 1_000_000 * 18;

    return {
      proyectos: rows.length,
      inputTokens,
      outputTokens,
      totalTokens,
      avgTokensPerProject,
      estimatedCost
    };
  }

  async listStorageFiles(bucket: string, folder: string): Promise<StorageFileItem[]> {
    if (!bucket) {
      return [];
    }
    const params = new URLSearchParams({ bucket, folder });
    const url = `${this.backendBaseUrl}/storage/files?${params.toString()}`;
    console.log('DashboardService.listStorageFiles requesting', url);
    const response = await fetch(url);

    if (!response.ok) {
      const detail = await response.text();
      console.error('DashboardService.listStorageFiles failed', { url, status: response.status, detail });
      throw new Error(detail || 'No se pudieron cargar los archivos desde Storage');
    }

    const payload = await response.json() as { files?: StorageFileItem[] };
    console.log('DashboardService.listStorageFiles payload files_count', (payload.files || []).length);
    return (payload.files ?? [])
      .filter((file) => /\.(glb|gltf)$/i.test(file.name))
      .map((file) => {
        const size = Number(file.size ?? 0);
        const compressedSize = size > 0 ? Math.floor(size * 0.22) : 0;
        const ratio = size > 0 ? Number(((size - compressedSize) / size * 100).toFixed(1)) : 0;
        return {
          ...file,
          size,
          estimatedCompressedSize: compressedSize,
          compressionRatio: ratio,
        };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  async replaceStorageFile(bucket: string, path: string, file: File): Promise<{ size: number }> {
    const form = new FormData();
    form.append('bucket', bucket);
    form.append('path', path);
    form.append('file', file);

    const response = await fetch(`${this.backendBaseUrl}/storage/files/replace`, {
      method: 'POST',
      body: form
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || 'No se pudo reemplazar el archivo en Storage');
    }

    return await response.json() as { size: number };
  }

  async optimizeStorageFile(bucket: string, path: string): Promise<{ original_size: number; compressed_size: number }> {
    const form = new FormData();
    form.append('bucket', bucket);
    form.append('path', path);

    const response = await fetch(`${this.backendBaseUrl}/storage/files/optimize`, {
      method: 'POST',
      body: form
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || 'No se pudo optimizar el archivo en el servidor');
    }

    return await response.json() as { original_size: number; compressed_size: number };
  }
}
