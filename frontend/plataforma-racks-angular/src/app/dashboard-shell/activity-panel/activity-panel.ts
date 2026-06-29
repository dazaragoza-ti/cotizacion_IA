import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-activity-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './activity-panel.html',
  styleUrl: './activity-panel.scss'
})
export class ActivityPanelComponent {
  @Input() items: string[] = [];
}
