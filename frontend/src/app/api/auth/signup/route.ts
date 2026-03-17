import { NextResponse } from 'next/server';
import fs from 'fs/promises';
import path from 'path';

const dataFilePath = path.join(process.cwd(), 'src', 'data.json');

export async function POST(req: Request) {
  try {
    const { name, email, password, role } = await req.json();

    if (!name || !email || !password) {
      return NextResponse.json({ error: 'Name, email, and password are required' }, { status: 400 });
    }

    // Read existing data
    let data: { users: any[] } = { users: [] };
    try {
      const fileContents = await fs.readFile(dataFilePath, 'utf8');
      data = JSON.parse(fileContents);
    } catch (err: any) {
      // If file doesn't exist, we will create it
      if (err.code !== 'ENOENT') {
        throw err;
      }
    }

    // Check if user exists
    if (data.users.some((u: any) => u.email === email)) {
      return NextResponse.json({ error: 'User already exists' }, { status: 409 });
    }

    // Create new user
    const newUser = {
      id: Date.now().toString(),
      name,
      email,
      password,
      role: role || 'user',
    };

    data.users.push(newUser);

    // Save to file
    await fs.writeFile(dataFilePath, JSON.stringify(data, null, 2));

    // Return success without password
    const { password: _, ...userWithoutPassword } = newUser;
    return NextResponse.json({ message: 'Signup successful', user: userWithoutPassword }, { status: 201 });
  } catch (error) {
    console.error('Signup error:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
