import { CommonModule } from '@angular/common';
import { Component, OnInit, ChangeDetectorRef, NgZone } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DashboardService, StorageFileItem } from '../services/dashboard.service';
// Server-side compression: no client-side GLTF/Draco transforms needed

type ModuleKey = 'analiticas' | 'alimentar' | 'draco';

@Component({
  selector: 'app-dashboard-shell',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard-shell.html',
  styleUrl: './dashboard-shell.scss'
})
export class DashboardShellComponent implements OnInit {
  activeModule: ModuleKey = 'analiticas';
  connected = false;
  connectionText = 'Desconectado';
  supabaseUrl = '';
  supabaseKey = '';
  stats: Array<{ label: string; value: string; hint: string }> = [];
  activity: string[] = [];
  usageBars: Array<{ label: string; value: string; percent: number; tone: string }> = [];
  summaryItems: Array<{ label: string; value: string }> = [];
  aiDocuments: StorageFileItem[] = [];
  dracoModels: StorageFileItem[] = [];
  selectedModelForReplace: StorageFileItem | null = null;
  replacementFile: File | null = null;
  replacementMessage = '';
  isReplacing = false;
  private readonly dracoEncoderPath = 'https://www.gstatic.com/draco/versioned/decoders/1.4.1/';

  isLoadingStorage = false;

  constructor(private dashboardService: DashboardService, private cdr: ChangeDetectorRef, private ngZone: NgZone) {}

  ngOnInit(): void {
    const searchParams = new URLSearchParams(window.location.search);
    const hashParams = new URLSearchParams(window.location.hash.substring(1));
    const savedUrl = localStorage.getItem('sb_url') ?? '';
    const savedKey = localStorage.getItem('sb_key') ?? '';

    const urlFromQuery = searchParams.get('sb_url') ?? hashParams.get('sb_url') ?? '';
    const keyFromQuery = searchParams.get('sb_key') ?? hashParams.get('sb_key') ?? '';

    this.supabaseUrl = urlFromQuery || savedUrl;
    this.supabaseKey = keyFromQuery || savedKey;

    if (this.supabaseUrl && this.supabaseKey) {
      void this.connectSupabase();
    }
  }

  async connectSupabase(): Promise<void> {
    this.activity = ['Conectando a Supabase...'];

    try {
      this.dashboardService.setConnection(this.supabaseUrl, this.supabaseKey);
      localStorage.setItem('sb_url', this.supabaseUrl);
      localStorage.setItem('sb_key', this.supabaseKey);
      await this.loadMetrics();
      this.connected = true;
      this.connectionText = 'Conexión Activa';

      try {
        await this.loadStorageContent();
      } catch (storageError) {
        console.warn('Conexión establecida, pero no se pudo cargar Storage:', storageError);
        this.activity.push('Conexión activa. No se pudieron cargar los archivos de Storage.');
      }
    } catch (error) {
      console.error('No se pudo conectar a Supabase', error);
      this.connected = false;
      this.connectionText = 'Desconectado';
      this.stats = [
        { label: 'Proyectos', value: '0', hint: 'Sin datos' },
        { label: 'Tokens', value: '0', hint: 'Sin datos' },
        { label: 'Costo estimado', value: '$0.00', hint: 'Sin datos' }
      ];
      this.usageBars = [];
      this.summaryItems = [];
      this.activity = ['No fue posible conectar a Supabase. Revisa la URL y la anon key.'];
    }
  }

  async loadMetrics(): Promise<void> {
    try {
      const metrics = await this.dashboardService.getMetrics();
      const totalTokens = Math.max(metrics.totalTokens, 1);
      const inputPercent = Math.round((metrics.inputTokens / totalTokens) * 100);
      const outputPercent = Math.round((metrics.outputTokens / totalTokens) * 100);

      this.stats = [
        { label: 'Proyectos', value: metrics.proyectos.toString(), hint: 'Registros en disenos_racks' },
        { label: 'Tokens', value: metrics.totalTokens.toLocaleString(), hint: 'Entrada + salida' },
        { label: 'Costo estimado', value: `$${metrics.estimatedCost.toFixed(2)}`, hint: 'Basado en uso real' }
      ];

      this.usageBars = [
        { label: 'Input tokens', value: `${metrics.inputTokens.toLocaleString()} tokens`, percent: inputPercent, tone: 'cyan' },
        { label: 'Output tokens', value: `${metrics.outputTokens.toLocaleString()} tokens`, percent: outputPercent, tone: 'violet' }
      ];

      this.summaryItems = [
        { label: 'Tokens totales', value: metrics.totalTokens.toLocaleString() },
        { label: 'Promedio por proyecto', value: Math.round(metrics.avgTokensPerProject).toLocaleString() },
        { label: 'Costo estimado', value: `$${metrics.estimatedCost.toFixed(2)}` }
      ];

      this.activity = [
        `Se cargaron ${metrics.proyectos} proyectos desde Supabase`,
        `Total de tokens procesados: ${metrics.totalTokens.toLocaleString()}`,
        `Promedio por diseño: ${Math.round(metrics.avgTokensPerProject).toLocaleString()} tokens`
      ];
    } catch (error) {
      console.error('No se pudieron cargar las métricas de Supabase', error);
      this.stats = [
        { label: 'Proyectos', value: '0', hint: 'Sin datos' },
        { label: 'Tokens', value: '0', hint: 'Sin datos' },
        { label: 'Costo estimado', value: '$0.00', hint: 'Sin datos' }
      ];
      this.usageBars = [];
      this.summaryItems = [];
      this.activity = ['No fue posible cargar métricas desde Supabase.'];
    }
  }

  async loadStorageContent(): Promise<void> {
    if (this.isLoadingStorage) {
      console.log('loadStorageContent: ya está en curso, ignorando llamada concurrente');
      return;
    }

    this.isLoadingStorage = true;
    try {
      console.log('loadStorageContent: solicitando listados al backend...');
      const [quotesFiles, pricesFiles, modelFiles, rootModelFiles] = await Promise.all([
        this.dashboardService.listStorageFiles('cotizaciones', 'Racks'),
        this.dashboardService.listStorageFiles('precios unitarios', 'productos'),
        this.dashboardService.listStorageFiles('modelos', 'modelos 3d de racks'),
        this.dashboardService.listStorageFiles('modelos', '')
      ]);
      console.log('loadStorageContent: responses', {
        quotes: quotesFiles?.length ?? 0,
        prices: pricesFiles?.length ?? 0,
        models: modelFiles?.length ?? 0,
        rootModels: rootModelFiles?.length ?? 0
      });

      const uniqueModelFiles = [...modelFiles, ...rootModelFiles].filter((item, index, array) =>
        index === array.findIndex((candidate) => candidate.path === item.path)
      );

      // Asegurar que la actualización de arrays se ejecute dentro de la zona de Angular
      this.ngZone.run(() => {
        this.aiDocuments = [...quotesFiles, ...pricesFiles].sort((a, b) => a.name.localeCompare(b.name));
        this.dracoModels = uniqueModelFiles.sort((a, b) => a.name.localeCompare(b.name));
        try { this.cdr.detectChanges(); } catch (e) { /* ignore */ }
      });
    } catch (error) {
      console.warn('No se pudieron cargar los archivos desde Supabase Storage', error);
      console.error('loadStorageContent error detalle:', error);
      this.ngZone.run(() => {
        if (!this.aiDocuments.length) {
          this.aiDocuments = [];
        }
        if (!this.dracoModels.length) {
          this.dracoModels = [];
        }
        this.activity.push('No se pudieron cargar los archivos de Storage en el módulo activo.');
        try { this.cdr.detectChanges(); } catch (e) { /* ignore */ }
      });
    } finally {
      this.isLoadingStorage = false;
    }
  }

  async switchModule(target: ModuleKey): Promise<void> {
    this.activeModule = target;

    // Cuando el usuario cambia a los módulos que muestran Storage, asegurar
    // que los archivos se recarguen. Si no hay conexión registrada, intentar
    // reconectar automáticamente si hay credenciales guardadas.
    if (target === 'draco' || target === 'alimentar') {
      if (!this.connected) {
        // Si hay credenciales en memoria (o en localStorage), intentar reconectar.
        const savedUrl = this.supabaseUrl || localStorage.getItem('sb_url') || '';
        const savedKey = this.supabaseKey || localStorage.getItem('sb_key') || '';
        if (savedUrl && savedKey) {
          try {
            this.supabaseUrl = savedUrl;
            this.supabaseKey = savedKey;
            await this.connectSupabase();
          } catch (connErr) {
            console.warn('No fue posible reconectar automáticamente al cambiar de módulo', connErr);
          }
        }
      }

      // Intentar cargar el contenido del Storage aunque no haya conexión activa;
      // la función internamente maneja errores y no romperá la UI.
      try {
        await this.loadStorageContent();
      } catch (error) {
        console.warn('No se pudieron recargar los archivos al cambiar de módulo', error);
      }
    }
  }

  async selectModelForReplace(model: StorageFileItem): Promise<void> {
    this.selectedModelForReplace = model;
    this.replacementFile = null;
    this.replacementMessage = '';
  }

  async forceReloadModels(): Promise<void> {
    console.log('forceReloadModels: manual reload triggered');
    try {
      await this.loadStorageContent();
      console.log('forceReloadModels: dracoModels count', this.dracoModels.length, 'models:', this.dracoModels.map(m => m.name));
      this.ngZone.run(() => { try { this.cdr.detectChanges(); } catch (e) {} });
    } catch (e) {
      console.error('forceReloadModels error', e);
    }
  }

  async autoOptimizeModel(model: StorageFileItem): Promise<void> {
    this.selectedModelForReplace = model;
    this.replacementFile = null;
    this.replacementMessage = 'Solicitando optimización al servidor...';
    this.isReplacing = true;

    try {
      const result = await this.dashboardService.optimizeStorageFile(model.bucket, model.path);
      const originalSize = result.original_size;
      const newSize = result.compressed_size;
      const reduction = originalSize > 0
        ? Number((((originalSize - newSize) / originalSize) * 100).toFixed(1))
        : 0;

      this.ngZone.run(() => {
        this.replacementMessage = `Optimización en servidor completa: ${this.formatBytes(newSize)} (${reduction}% reducción).`;
      });

      // Recargar lista y forzar renderizado
      await this.loadStorageContent();
      try { this.cdr.detectChanges(); } catch (e) { /* ignore */ }
    } catch (error) {
      console.error('autoOptimizeModel (server) error', error);
      this.ngZone.run(() => {
        this.replacementMessage = `Error al optimizar en servidor: ${error instanceof Error ? error.message : 'Error desconocido'}`;
      });
    } finally {
      this.ngZone.run(() => { this.isReplacing = false; });
    }
  }

  onReplacementFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    if (file) {
      this.replacementFile = file;
      this.replacementMessage = `Archivo seleccionado: ${file.name} (${this.formatBytes(file.size)})`;
    } else {
      this.replacementFile = null;
      this.replacementMessage = '';
    }
  }

  async compressAndReplace(): Promise<void> {
    if (!this.selectedModelForReplace) {
      this.replacementMessage = 'Selecciona un modelo antes de reemplazarlo.';
      return;
    }

    if (!this.replacementFile) {
      this.replacementMessage = 'Selecciona un archivo .glb o .gltf comprimido para reemplazar.';
      return;
    }

    this.isReplacing = true;
    this.replacementMessage = 'Subiendo archivo y reemplazando el modelo...';

    try {
      const result = await this.dashboardService.replaceStorageFile(
        this.selectedModelForReplace.bucket,
        this.selectedModelForReplace.path,
        this.replacementFile
      );

      const originalSize = this.selectedModelForReplace.size;
      const newSize = result.size;
      const reduction = originalSize > 0
        ? Number((((originalSize - newSize) / originalSize) * 100).toFixed(1))
        : 0;

      this.selectedModelForReplace.size = newSize;
      this.selectedModelForReplace.estimatedCompressedSize = newSize;
      this.selectedModelForReplace.compressionRatio = reduction;
      this.selectedModelForReplace.url = this.selectedModelForReplace.url;

      this.replacementMessage = `Reemplazo completado: nuevo peso ${this.formatBytes(newSize)} (${reduction}% de reducción).`;
      await this.loadStorageContent();
    } catch (error) {
      console.error(error);
      this.replacementMessage = 'Error al reemplazar el archivo. Revisa la consola para más detalles.';
    } finally {
      this.isReplacing = false;
    }
  }

  formatBytes(bytes: number): string {
    if (bytes === 0) { return '0 B'; }
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
  }

  refreshMetrics(): void {
    if (this.supabaseUrl && this.supabaseKey) {
      void this.connectSupabase();
    } else {
      this.activity = ['Ingresa la URL y la anon key de Supabase para cargar los datos.'];
    }
  }
}
