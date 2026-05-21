export function formatTimestamp(timestamp: number | string): string {
    const ts = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp
    const date = new Date(ts * 1000)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`
}

export function formatTimestampMs(timestamp: number): string {
    const date = new Date(timestamp)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`
}

export function splitwid(num: number): string {
    const numStr = num.toString()
    const lastFour = numStr.slice(-4)
    const firstPart = numStr.slice(0, -4)
    const lastFourNumber = parseInt(lastFour, 10)
    return `${firstPart},${lastFourNumber}`
}
