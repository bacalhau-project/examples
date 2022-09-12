import { readCSVRows, writeCSV } from "./deps.ts"
import { path } from "./deps.ts"

const filename = Deno.env.get("FILE_TO_PROCESS")!;
if (filename == null) {
    throw new Error("No file to process. Please set FILE_TO_PROCESS environment variable.");
}
let outputDir = Deno.env.get("OUTPUT_DIR")!;
if (outputDir == null) {
    outputDir = "/outputs";
}
const f = await Deno.open(filename);

const filesToWrite: Map<string, Deno.FsFile> = new Map();

let i = 0
let header: string[] = []; // header row

for await (const row of readCSVRows(f)) {
    const asyncRowGenerator = async function*(r: string[]) {
        yield r;
    }

    if (i === 0) {
        i++;
        header = row;
        continue;
    }
    
    const numPassengers = parseInt(row[6]);
    const fileName = path.join(outputDir, `passengers_${numPassengers}.csv`);
    
    let fileWriter = await filesToWrite.get(fileName)!
    if (!fileWriter) {
        fileWriter = await Deno.open(fileName,
            { write: true, create: true, append: true, read: true, truncate: false, mode: 0o666 });
        await writeCSV(fileWriter, asyncRowGenerator(header));
        await filesToWrite.set(fileName, fileWriter)
    }

    await writeCSV(fileWriter, asyncRowGenerator(row));
    i++;
}

for (const file of filesToWrite.values()) {
    file.close();
}
