import electron, { dialog } from 'electron';

export declare interface Is {
  dev: boolean;
  macOS: boolean;
  windows: boolean;
}

export const is: Is = {
  dev: !electron.app.isPackaged,
  macOS: process.platform === 'darwin',
  windows: process.platform === 'win32'
};

export function generateAlphaNumericString(length: number = 0): string {
  if (length <= 0) {
    throw new Error('Length must be greater than 0');
  }

  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += characters.charAt(Math.floor(Math.random() * characters.length));
  }
  return result;
}

export async function waitForBackendReady(timeout = 60000, interval = 250): Promise<void> {
  const start = Date.now();

  while (Date.now() - start < timeout) {
    try {
      const res = await fetch('http://127.0.0.1:8000/health', { method: 'GET' });
      if (res.ok) {
        return;
      }
    } catch (e) {
      // Backend not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
  throw new Error(`Backend did not become ready within ${timeout} ms`);
}
