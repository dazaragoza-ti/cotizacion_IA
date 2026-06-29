import { Component } from '@angular/core';
import { DashboardShellComponent } from './dashboard-shell/dashboard-shell';

@Component({
  selector: 'app-root',
  imports: [DashboardShellComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {}
