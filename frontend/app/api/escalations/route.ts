import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import path from 'path';
import { promisify } from 'util';

const execAsync = promisify(exec);
const backendDir = path.resolve(process.cwd(), '../backend');

// Don't cache escalation API responses
export const revalidate = 0;

export async function GET() {
  try {
    const pyScript = `import json, sys; sys.path.insert(0, 'src'); from memory import db_list_escalations; print(json.dumps(db_list_escalations()))`;
    const { stdout } = await execAsync(`uv run python -c "${pyScript}"`, { cwd: backendDir });
    const data = JSON.parse(stdout.trim() || '[]');
    return NextResponse.json({ success: true, escalations: data });
  } catch (error: unknown) {
    const errMessage = error instanceof Error ? error.message : 'Failed to query database';
    console.error('Failed to fetch escalations:', error);
    return NextResponse.json(
      { success: false, error: errMessage, escalations: [] },
      { status: 500 }
    );
  }
}

export async function PATCH(req: Request) {
  try {
    const body = await req.json();
    const { reference_id, status } = body;
    if (!reference_id || !status) {
      return NextResponse.json(
        { success: false, error: 'Missing reference_id or status' },
        { status: 400 }
      );
    }
    const pyScript = `import json, sys; sys.path.insert(0, 'src'); from memory import db_update_escalation_status; print(json.dumps(db_update_escalation_status('${reference_id}', '${status}')))`;
    const { stdout } = await execAsync(`uv run python -c "${pyScript}"`, { cwd: backendDir });
    const updated = stdout.trim() === 'true';
    return NextResponse.json({ success: updated });
  } catch (error: unknown) {
    const errMessage = error instanceof Error ? error.message : 'Failed to update escalation';
    console.error('Failed to update escalation status:', error);
    return NextResponse.json({ success: false, error: errMessage }, { status: 500 });
  }
}
