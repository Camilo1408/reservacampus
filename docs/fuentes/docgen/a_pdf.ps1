# Actualiza índices/campos de cada .docx con Word y lo exporta a PDF (una instancia de Word por archivo).
# Uso: powershell -File docs/fuentes/docgen/a_pdf.ps1 [nombre.docx ...]
param([string[]]$Archivos)
$dir = Resolve-Path (Join-Path $PSScriptRoot "..\..\entregables")
if (-not $Archivos) { $Archivos = Get-ChildItem $dir -Filter *.docx | ForEach-Object { $_.Name } }
foreach ($a in $Archivos) {
  $ruta = Join-Path $dir $a
  $pdf = [System.IO.Path]::ChangeExtension($ruta, ".pdf")
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0
  try {
    $doc = $word.Documents.Open($ruta, $false, $false)
    $doc.Fields.Update() | Out-Null
    foreach ($t in $doc.TablesOfContents) { $t.Update() }
    $doc.Save()
    $doc.ExportAsFixedFormat($pdf, 17)   # 17 = wdExportFormatPDF
    Write-Output ("pdf: " + $pdf)
    try { $doc.Close($false) } catch { }
  } catch {
    Write-Output ("error en " + $a + ": " + $_.Exception.Message)
  } finally {
    try { $word.Quit() } catch { }
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    Start-Sleep -Milliseconds 800
  }
}
