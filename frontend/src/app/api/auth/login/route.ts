import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const dataFilePath = path.join(process.cwd(), 'src', 'data.json');

type UserRecord = {
  id: string;
  name: string;
  email: string;
  password: string;
  role?: string;
};

type UserData = {
  users: UserRecord[];
};

function withoutPassword(user: UserRecord) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    role: user.role,
  };
}

export async function POST(req: Request) {
  try {
    const { email, password } = await req.json();

    if (!email || !password) {
      return NextResponse.json({ error: 'Email and password are required' }, { status: 400 });
    }

    const fileContents = await fs.readFile(dataFilePath, 'utf8');
    const data = JSON.parse(fileContents) as UserData;

    const user = data.users.find((u) => u.email === email && u.password === password);

    if (user) {
      return NextResponse.json({ message: 'Login successful', user: withoutPassword(user) }, { status: 200 });
    } else {
      return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
    }
  } catch (error) {
    console.error('Login error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
