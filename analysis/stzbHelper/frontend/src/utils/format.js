/**
 * 将秒级时间戳转换为可读日期字符串
 * @param {number} timestamp - 秒级时间戳
 * @returns {string} 格式化后的日期字符串
 */
export function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * 将毫秒级时间戳转换为可读日期字符串
 * @param {number} timestamp - 毫秒级时间戳
 * @returns {string} 格式化后的日期字符串
 */
export function formatTimestampMs(timestamp) {
    const date = new Date(timestamp);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * 将位置数字格式化为坐标字符串
 * @param {number} num - 位置数字
 * @returns {string} 格式化后的坐标
 */
export function splitwid(num) {
    const numStr = num.toString();
    const lastFour = numStr.slice(-4);
    const firstPart = numStr.slice(0, -4);
    const lastFourNumber = parseInt(lastFour, 10);
    return `${firstPart},${lastFourNumber}`;
}
