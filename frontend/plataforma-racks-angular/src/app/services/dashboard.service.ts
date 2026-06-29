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

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private supabase: SupabaseClient | null = null;

  setConnection(url: string, key: string): void {
    const supabaseUrl = url.trim();
    const supabaseKey = key.trim();

    if (!supabaseUrl || !supabaseKey) {
      throw new Error('Falta la URL o la anon key de Supabase');
    }

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
}
