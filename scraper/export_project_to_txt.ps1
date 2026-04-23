$root = Get-Location
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputFile = Join-Path $root "projekt_code_export_$timestamp.txt"

# Dateitypen, die wahrscheinlich relevant sind
$extensions = @(
    "*.py", "*.js", "*.ts", "*.json", "*.yaml", "*.yml",
    "*.toml", "*.ini", "*.cfg", "*.env", "*.ps1", "*.bat",
    "*.cmd", "*.md", "*.txt", "*.sql", "*.html", "*.css"
)

# Ordner, die oft groß oder unnötig sind
$excludeDirs = @(
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".mypy_cache", ".pytest_cache", "dist", "build"
)

"PROJECT EXPORT" | Set-Content -Path $outputFile -Encoding UTF8
"Root: $root" | Add-Content -Path $outputFile -Encoding UTF8
"Created: $(Get-Date)" | Add-Content -Path $outputFile -Encoding UTF8
"" | Add-Content -Path $outputFile -Encoding UTF8

Get-ChildItem -Path $root -Recurse -File -Include $extensions | Where-Object {
    $full = $_.FullName
    -not ($excludeDirs | ForEach-Object { $full -match [regex]::Escape("\$_\") -or $full -match [regex]::Escape("/$_/") } | Where-Object { $_ })
} | Sort-Object FullName | ForEach-Object {
    $relativePath = $_.FullName.Substring($root.Path.Length).TrimStart('\')
    
    Add-Content -Path $outputFile -Encoding UTF8 -Value ("=" * 120)
    Add-Content -Path $outputFile -Encoding UTF8 -Value ("FILE: " + $relativePath)
    Add-Content -Path $outputFile -Encoding UTF8 -Value ("FULL PATH: " + $_.FullName)
    Add-Content -Path $outputFile -Encoding UTF8 -Value ("SIZE: " + $_.Length + " bytes")
    Add-Content -Path $outputFile -Encoding UTF8 -Value ("=" * 120)
    Add-Content -Path $outputFile -Encoding UTF8 -Value ""

    try {
        Get-Content -Path $_.FullName -Raw -ErrorAction Stop | Add-Content -Path $outputFile -Encoding UTF8
    }
    catch {
        Add-Content -Path $outputFile -Encoding UTF8 -Value "[FEHLER BEIM LESEN DER DATEI]"
        Add-Content -Path $outputFile -Encoding UTF8 -Value $_.Exception.Message
    }

    Add-Content -Path $outputFile -Encoding UTF8 -Value ""
    Add-Content -Path $outputFile -Encoding UTF8 -Value ""
}

Write-Host "Fertig. Export erstellt:"
Write-Host $outputFile