'use client'

import { useSearchParams, useRouter } from 'next/navigation'
import { useEffect, useState, Suspense } from 'react'
import { createClient } from '@supabase/supabase-js'

function ConfirmContent() {
  const searchParams = useSearchParams()
  const router = useRouter()

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const run = async () => {
      try {
        const token_hash = searchParams.get('token_hash')
        const type = searchParams.get('type') // expect email

        if (!token_hash || !type) {
          setError('Missing token_hash or type in the link.')
          return
        }

        const supabase = createClient(
          process.env.NEXT_PUBLIC_SUPABASE_URL as string,
          process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY as string
        )

        const { error } = await supabase.auth.verifyOtp({
          type: type as 'email',
          token_hash
        })

        if (error) {
          setError(error.message)
          return
        }

        router.replace('/')
      } catch (e: any) {
        setError(e?.message ?? 'Failed to confirm.')
      } finally {
        setLoading(false)
      }
    }

    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) return <p>Confirming your email</p>

  return (
    <div>
      {error ? (
        <p style={{ color: 'crimson' }}>{error}</p>
      ) : (
        <p>Email confirmed Redirecting</p>
      )}
    </div>
)
}

export default function ConfirmPage() {
  return (
    <Suspense fallback={<p>Confirming your email</p>}>
      <ConfirmContent />
    </Suspense>
  )
}
