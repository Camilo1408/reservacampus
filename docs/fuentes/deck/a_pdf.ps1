# Exporta la presentación a PDF con PowerPoint.
$ppt = Resolve-Path (Join-Path $PSScriptRoot "..\..\entregables\07_Presentacion_Final.pptx")
$pdf = [System.IO.Path]::ChangeExtension($ppt, ".pdf")
$app = New-Object -ComObject PowerPoint.Application
try {
  $p = $app.Presentations.Open($ppt, $true, $false, $false)
  $p.SaveAs($pdf, 32)   # 32 = ppSaveAsPDF
  $p.Close()
  Write-Output ("pdf: " + $pdf)
} finally { try { $app.Quit() } catch { } }
