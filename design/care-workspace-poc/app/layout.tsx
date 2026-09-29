import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  metadataBase: new URL('https://viet-uc-care-workspace-concept.groovy-pixie-4012.chatgpt.site'),
  title: 'Viet UC · Care workspace',
  description: 'A considered workspace for contacts, bookings and client care. Interactive design concept.',
  openGraph: {title:'Viet UC · Care workspace',description:'Care, connected. A considered care workspace.',images:['/og.png']},
  twitter: {card:'summary_large_image',title:'Viet UC · Care workspace',description:'Care, connected. A considered care workspace.',images:['/og.png']},
};
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
