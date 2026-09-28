import { describe, expect, it } from 'vitest';
import { nearBottom, submitsMessage, taskLabels } from '../src/renderer/chat-state';

describe('M11 reading and keyboard boundaries', () => {
  it('keeps readers in history, follows only near the bottom', () => {
    expect(nearBottom(20, 300, 1200)).toBe(false);
    expect(nearBottom(850, 300, 1200)).toBe(true);
  });
  it('does not send IME confirmation or newline', () => {
    expect(submitsMessage('Enter', false, true, 13)).toBe(false);
    expect(submitsMessage('Enter', false, false, 229)).toBe(false);
    expect(submitsMessage('Enter', true, false, 13)).toBe(false);
    expect(submitsMessage('Enter', false, false, 13)).toBe(true);
  });
  it('distinguishes unfinished tasks and terminal outcomes', () => {
    expect(new Set(['draft','running','awaiting_approval','completed','failed','interrupted','undone'].map(s => taskLabels[s])).size).toBe(7);
  });
});
