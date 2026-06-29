import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DashboardService, StorageFileItem } from '../services/dashboard.service';

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

  constructor(private dashboardService: DashboardService) {}

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
      await this.loadStorageContent();
      this.connected = true;
      this.connectionText = 'Conexión Activa';
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
    try {
      const [quotesFiles, pricesFiles, modelFiles] = await Promise.all([
        this.dashboardService.listStorageFiles('cotizaciones', 'Racks'),
        this.dashboardService.listStorageFiles('precios unitarios', 'productos'),
        this.dashboardService.listStorageFiles('modelos', 'modelos 3d de racks')
      ]);

      this.aiDocuments = [...quotesFiles, ...pricesFiles].sort((a, b) => a.name.localeCompare(b.name));
      this.dracoModels = modelFiles.sort((a, b) => a.name.localeCompare(b.name));
    } catch (error) {
      console.warn('No se pudieron cargar los archivos desde Supabase Storage', error);
      this.aiDocuments = [];
      this.dracoModels = [];
    }
  }

  switchModule(target: ModuleKey): void {
    this.activeModule = target;
  }

  refreshMetrics(): void {
    if (this.supabaseUrl && this.supabaseKey) {
      void this.connectSupabase();
    } else {
      this.activity = ['Ingresa la URL y la anon key de Supabase para cargar los datos.'];
    }
  }
}
