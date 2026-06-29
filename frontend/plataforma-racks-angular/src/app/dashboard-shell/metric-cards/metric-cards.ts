import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-metric-cards',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './metric-cards.html',
  styleUrl: './metric-cards.scss'
})
export class MetricCardsComponent {
  @Input() items: Array<{ label: string; value: string; hint: string }> = [];
}
