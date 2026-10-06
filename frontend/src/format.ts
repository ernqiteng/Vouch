// Shared date formatting, in British English and the viewer's own time zone.

const day = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
const dayWithYear = new Intl.DateTimeFormat('en-GB', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })
const stamp = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' })

export const formatDay = (iso: string) => day.format(new Date(iso))
export const formatDayWithYear = (iso: string) => dayWithYear.format(new Date(iso))
export const formatTime = (iso: string) => clock.format(new Date(iso))
export const formatTimeRange = (start: string, end: string) => `${formatTime(start)}–${formatTime(end)}`
export const formatStamp = (iso: string) => stamp.format(new Date(iso))
export const percent = (value: number) => `${Math.round(value * 100)}%`
