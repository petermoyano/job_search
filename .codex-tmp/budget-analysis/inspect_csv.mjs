import fs from "node:fs/promises";
import { Workbook } from "@oai/artifact-tool";

const sourcePath = "C:/Users/Admin/Downloads/budgets.csv";
const csvText = await fs.readFile(sourcePath, "utf8");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "AWS export" });
const sheet = workbook.worksheets.getItem("AWS export");
const used = sheet.getUsedRange(true);
const values = used?.values ?? [];

const inspection = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 12000,
  tableMaxRows: 100,
  tableMaxCols: 40,
  tableMaxCellChars: 200,
});

console.log(JSON.stringify({
  sourcePath,
  bytes: Buffer.byteLength(csvText),
  rowCount: values.length,
  columnCount: values[0]?.length ?? 0,
  headers: values[0] ?? [],
  values,
  inspection: inspection.ndjson,
}, null, 2));
