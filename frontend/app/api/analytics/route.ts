import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';
import { promisify } from 'util';

const execAsync = promisify(exec);
const backendDir = path.resolve(process.cwd(), '../backend');

// Disable static caching for real-time analytics polling
export const revalidate = 0;

export async function GET() {
  try {
    const pyScript = `import json, sys; sys.path.insert(0, 'src'); from memory import db_get_analytics_summary, db_get_recent_calls; summary = db_get_analytics_summary(); recent = db_get_recent_calls(50); print(json.dumps({'summary': summary, 'recent_calls': recent}))`;

    const { stdout } = await execAsync(`uv run python -c "${pyScript}"`, { cwd: backendDir });
    const data = JSON.parse(stdout.trim() || '{}');

    return NextResponse.json({
      success: true,
      summary: data.summary || {
        total_calls: 0,
        successful_calls: 0,
        failed_calls: 0,
        success_rate: 0.0,
        by_success_type: {},
        by_channel: {},
      },
      recent_calls: data.recent_calls || [],
    });
  } catch (error: unknown) {
    const errMessage =
      error instanceof Error ? error.message : 'Failed to query analytics database';
    console.error('Failed to fetch call analytics:', error);
    return NextResponse.json(
      {
        success: false,
        error: errMessage,
        summary: {
          total_calls: 0,
          successful_calls: 0,
          failed_calls: 0,
          success_rate: 0.0,
          by_success_type: {},
          by_channel: {},
        },
        recent_calls: [],
      },
      { status: 500 }
    );
  }
}
