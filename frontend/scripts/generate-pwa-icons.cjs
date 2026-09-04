// Original geometric LegalFlow monogram. Deterministic PNGs, no remote asset or dependency.
const { deflateSync } = require("node:zlib");
const { mkdirSync, writeFileSync } = require("node:fs");
const { join } = require("node:path");
const output = join(__dirname, "../public/icons");
mkdirSync(output, { recursive: true });
function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) { crc ^= byte; for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1)); }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const name = Buffer.from(type), length = Buffer.alloc(4), crc = Buffer.alloc(4);
  length.writeUInt32BE(data.length); crc.writeUInt32BE(crc32(Buffer.concat([name, data])));
  return Buffer.concat([length, name, data, crc]);
}
for (const [size, filename] of [[192, "icon-192.png"], [512, "icon-512.png"], [180, "apple-touch-icon.png"]]) {
  const raw = Buffer.alloc(size * (size * 3 + 1));
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const u = x / size, v = y / size;
    // All foreground lies within the central maskable safe zone.
    const letter = (u >= .29 && u <= .37 && v >= .28 && v <= .70) || (u >= .29 && u <= .58 && v >= .62 && v <= .70);
    const flow = u >= .46 && u <= .70 && ((v >= .30 && v <= .38) || (v >= .45 && v <= .53));
    const color = letter ? [250, 250, 250] : flow ? [96, 165, 250] : [9, 9, 11];
    const offset = y * (size * 3 + 1) + 1 + x * 3;
    raw[offset] = color[0]; raw[offset + 1] = color[1]; raw[offset + 2] = color[2];
  }
  const header = Buffer.alloc(13); header.writeUInt32BE(size); header.writeUInt32BE(size, 4); header[8] = 8; header[9] = 2;
  writeFileSync(join(output, filename), Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", header), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]));
}
