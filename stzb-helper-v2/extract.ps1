$word = New-Object -ComObject Word.Application
$word.Visible = $false
$doc = $word.Documents.Open("$PWD\temp.docx")
foreach ($p in $doc.Paragraphs) {
    $t = $p.Range.Text.Trim()
    if ($t) {
        Write-Output $t
    }
}
$doc.Close()
$word.Quit()
