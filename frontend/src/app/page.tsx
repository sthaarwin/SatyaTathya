import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import Dashboard from './Dashboard';

export default async function Home() {
  const cookieStore = await cookies();
  const token = cookieStore.get('sb-access-token');

  if (!token) {
    redirect('/auth');
  }

  return <Dashboard />;
}
