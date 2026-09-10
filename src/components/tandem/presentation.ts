const memberColors = ['#8f4357', '#b86d57', '#7d8c73', '#b58b4c', '#487276']

export function memberColor(index: number): string {
  return memberColors[index % memberColors.length]
}

export function formatParticipantNames(names: string[]): string {
  if (!names.length) return 'No participants selected'
  if (names.length === 1) return names[0]
  if (names.length === 2) return `${names[0]} and ${names[1]}`
  return `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`
}
