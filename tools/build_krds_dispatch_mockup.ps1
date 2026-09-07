# Creates a standalone vector design draft and a matching preview. No app imports.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path $projectRoot 'docs/design'
[System.IO.Directory]::CreateDirectory($outputDir) | Out-Null
$script:svg = [System.Collections.Generic.List[string]]::new()
$script:layerNumber = 0
$script:bitmap = [System.Drawing.Bitmap]::new(1440, 1360)
$script:graphics = [System.Drawing.Graphics]::FromImage($script:bitmap)
$script:graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$script:fontFamily = [System.Drawing.FontFamily]::new('Malgun Gothic')
$script:format = [System.Drawing.StringFormat]::GenericTypographic
$script:svg.Add('<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1360" viewBox="0 0 1440 1360">')
$script:svg.Add('<title>정보공개 청구 지원 시스템 — 배정 대기 디자인 초안</title>')
$script:svg.Add('<desc>KRDS 스타일을 참고한 벡터 시안. 합성 예시이며 텍스트는 글꼴 호환성을 위해 윤곽선으로 저장함. 공식 컴포넌트 인스턴스와 자동 레이아웃은 포함하지 않음.</desc>')

function Number([single]$value) {
    return $value.ToString('0.###', [System.Globalization.CultureInfo]::InvariantCulture)
}
function Color([string]$value) {
    return [System.Drawing.ColorTranslator]::FromHtml($value)
}
function Box {
    param([single]$x, [single]$y, [single]$w, [single]$h, [string]$fill = '#FFFFFF', [string]$stroke = '', [single]$radius = 0)
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    if ($radius -gt 0) {
        $d = $radius * 2
        $path.AddArc($x, $y, $d, $d, 180, 90)
        $path.AddArc(($x + $w - $d), $y, $d, $d, 270, 90)
        $path.AddArc(($x + $w - $d), ($y + $h - $d), $d, $d, 0, 90)
        $path.AddArc($x, ($y + $h - $d), $d, $d, 90, 90)
        $path.CloseFigure()
    } else {
        $path.AddRectangle([System.Drawing.RectangleF]::new($x, $y, $w, $h))
    }
    $brush = [System.Drawing.SolidBrush]::new((Color $fill))
    $script:graphics.FillPath($brush, $path)
    $brush.Dispose()
    $strokeAttribute = ''
    if ($stroke) {
        $pen = [System.Drawing.Pen]::new((Color $stroke), 1)
        $script:graphics.DrawPath($pen, $path)
        $pen.Dispose()
        $strokeAttribute = " stroke=`"$stroke`""
    }
    $script:svg.Add("<rect x=`"$(Number $x)`" y=`"$(Number $y)`" width=`"$(Number $w)`" height=`"$(Number $h)`" rx=`"$(Number $radius)`" fill=`"$fill`"$strokeAttribute/>")
    $path.Dispose()
}
function Line {
    param([single]$x1, [single]$y1, [single]$x2, [single]$y2, [string]$color = '#E6E8EA', [single]$width = 1)
    $pen = [System.Drawing.Pen]::new((Color $color), $width)
    $script:graphics.DrawLine($pen, $x1, $y1, $x2, $y2)
    $pen.Dispose()
    $script:svg.Add("<path d=`"M $(Number $x1) $(Number $y1) L $(Number $x2) $(Number $y2)`" fill=`"none`" stroke=`"$color`" stroke-width=`"$(Number $width)`"/>")
}
function Text {
    param([single]$x, [single]$y, [string]$value, [single]$size = 17, [string]$color = '#1E2124', [bool]$bold = $false)
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $style = if ($bold) { [System.Drawing.FontStyle]::Bold } else { [System.Drawing.FontStyle]::Regular }
    $path.AddString($value, $script:fontFamily, [int]$style, $size, [System.Drawing.PointF]::new($x, $y), $script:format)
    $brush = [System.Drawing.SolidBrush]::new((Color $color))
    $script:graphics.FillPath($brush, $path)
    $brush.Dispose()
    $points = $path.PathPoints
    $types = $path.PathTypes
    $data = [System.Text.StringBuilder]::new()
    for ($i = 0; $i -lt $points.Length; $i++) {
        $type = $types[$i] -band 7
        if ($type -eq 0) {
            [void]$data.Append("M $(Number $points[$i].X) $(Number $points[$i].Y) ")
        } elseif ($type -eq 1) {
            [void]$data.Append("L $(Number $points[$i].X) $(Number $points[$i].Y) ")
        } elseif ($type -eq 3) {
            [void]$data.Append("C $(Number $points[$i].X) $(Number $points[$i].Y) $(Number $points[$i+1].X) $(Number $points[$i+1].Y) $(Number $points[$i+2].X) $(Number $points[$i+2].Y) ")
            $i += 2
        }
        if (($types[$i] -band 128) -ne 0) { [void]$data.Append('Z ') }
    }
    $script:layerNumber++
    $escaped = [System.Security.SecurityElement]::Escape($value)
    $script:svg.Add("<g id=`"text_$($script:layerNumber)`" aria-label=`"$escaped`"><title>$escaped</title><path fill=`"$color`" d=`"$data`"/></g>")
    $path.Dispose()
}
function SearchBox([single]$x, [single]$y, [single]$w) {
    Box $x $y $w 48 '#FFFFFF' '#8A949E' 6
    Text ($x + 16) ($y + 13) '이름·지역본부·지사·부서로 검색' 15 '#6D7882'
    $pen = [System.Drawing.Pen]::new((Color '#464C53'), 1.8)
    $script:graphics.DrawEllipse($pen, ($x + $w - 33), ($y + 15), 13, 13)
    $pen.Dispose()
    $script:svg.Add("<circle cx=`"$($x + $w - 26.5)`" cy=`"$($y + 21.5)`" r=`"6.5`" fill=`"none`" stroke=`"#464C53`" stroke-width=`"1.8`"/>")
    Line ($x + $w - 22) ($y + 27) ($x + $w - 16) ($y + 33) '#464C53' 1.8
}

# Application chrome and the dispatcher's actual navigation.
Box 0 0 1440 1360 '#F4F5F6'
Box 0 0 240 1360 '#122B46'
Box 240 0 1200 80 '#FFFFFF'
Line 240 80 1440 80
Box 24 30 32 32 '#FFFFFF' '' 6
Text 32 33 'K' 22 '#123F73' $true
Text 68 30 '한국전력공사' 18 '#FFFFFF' $true
Text 28 106 '정보공개' 27 '#FFFFFF' $true
Text 28 146 '청구지원 시스템' 22 '#FFFFFF' $true
Text 28 210 '업무 메뉴' 13 '#B3C5D8'
Box 16 244 208 52 '#FFFFFF' '' 8
Box 16 255 4 30 '#246BEB' '' 2
Text 40 257 '배정 대기' 18 '#174D9D' $true
Text 40 323 '청구 접수' 18 '#D6E2EF'
Line 24 1204 216 1204 '#35506B'
Text 28 1226 '정보공개 업무 지원' 14 '#D6E2EF'
Text 28 1251 'KEPCO' 13 '#A0B7CD'
Text 280 28 '정보공개 청구 지원 시스템' 18 '#1E2124' $true
Text 1062 30 'dispatcher · 배정담당자' 15 '#464C53'
Box 1295 22 104 36 '#FFFFFF' '#CDD1D5' 6
Text 1317 29 '로그아웃' 14 '#464C53'

# Heading: no invented statistics, filters, or bulk actions.
Text 280 115 '배정 대기' 34 '#1E2124' $true
Text 280 166 '접수된 청구 내용을 확인하고 업무담당자를 지정하세요.' 17 '#464C53'
Box 1214 123 186 48 '#246BEB' '' 6
Text 1234 135 '+ 새 청구 접수' 17 '#FFFFFF' $true
Text 280 226 '배정 대기 청구' 23 '#1E2124' $true
Box 448 229 44 30 '#E8F0FF' '' 15
Text 459 234 '2건' 15 '#174D9D' $true

# First request with a prepared recommendation, using synthetic content.
$script:svg.Add('<g id="request_101_with_recommendation">')
Box 280 280 1120 406 '#FFFFFF' '#CDD1D5' 12
Line 958 304 958 662
Text 304 304 '#101 김예시' 18 '#174D9D' $true
Box 444 304 66 27 '#F0F4F8' '' 4
Text 457 309 '미배정' 13 '#464C53'
Text 717 308 '2026.09.07 09:20 · txt' 14 '#6D7882'
Text 304 350 '2025년 지역별 전기차 충전시설 설치 현황' 23 '#1E2124' $true
Text 304 394 '청구 원문' 15 '#464C53' $true
Box 304 425 626 166 '#F7F8FA' '' 6
Text 324 449 '2025년 1월부터 12월까지 지역별 전기차 충전시설' 17 '#1E2124'
Text 324 479 '설치 현황을 요청합니다. 설치 장소, 설치 대수,' 17 '#1E2124'
Text 324 509 '운영 시작일을 포함하여 공개해 주시기 바랍니다.' 17 '#1E2124'
Text 304 630 '청구 상세 보기  →' 15 '#174D9D' $true
Text 984 306 '업무담당자 배정' 20 '#1E2124' $true
Text 984 341 '추천 담당자를 선택하면 바로 배정됩니다.' 14 '#464C53'
Box 984 373 392 45 '#ECF2FE' '#B1C9F5' 6
Text 999 385 '1순위' 14 '#174D9D' $true
Text 1063 383 'staff2' 17 '#174D9D' $true
Text 1336 383 '→' 18 '#174D9D'
Box 984 426 192 42 '#FFFFFF' '#CDD1D5' 6
Text 999 437 '2순위   staff5' 15 '#464C53'
Box 1184 426 192 42 '#FFFFFF' '#CDD1D5' 6
Text 1199 437 '3순위   staff8' 15 '#464C53'
Text 984 482 '추천 사유' 13 '#464C53' $true
Text 984 505 '충전시설 설치·운영 현황과 관련된 업무입니다.' 14 '#464C53'
Text 984 549 '담당자 검색' 15 '#1E2124' $true
SearchBox 984 578 392
Text 984 643 '검색 결과에서 담당자를 선택해 배정할 수 있습니다.' 13 '#6D7882'
$script:svg.Add('</g>')

# Second request with the recommendation button and the same assignment search.
$script:svg.Add('<g id="request_102_without_recommendation">')
Box 280 710 1120 282 '#FFFFFF' '#CDD1D5' 12
Line 958 734 958 968
Text 304 734 '#102 이예시' 18 '#174D9D' $true
Box 444 734 66 27 '#F0F4F8' '' 4
Text 457 739 '미배정' 13 '#464C53'
Text 717 738 '2026.09.07 10:05 · txt' 14 '#6D7882'
Text 304 780 '2025년 공공기관 전력 사용량 현황' 23 '#1E2124' $true
Box 304 828 626 100 '#F7F8FA' '' 6
Text 324 848 '2025년 공공기관의 월별 전력 사용량 현황과' 17 '#1E2124'
Text 324 878 '집계 기준에 관한 자료를 요청합니다.' 17 '#1E2124'
Text 304 949 '청구 상세 보기  →' 15 '#174D9D' $true
Text 984 736 '업무담당자 배정' 20 '#1E2124' $true
Box 984 779 392 46 '#FFFFFF' '#246BEB' 6
Text 1125 791 'AI 판단하기' 16 '#174D9D' $true
Text 984 851 '담당자 검색' 15 '#1E2124' $true
SearchBox 984 879 392
Text 984 950 '담당자를 직접 검색하여 배정할 수 있습니다.' 13 '#6D7882'
$script:svg.Add('</g>')

# Recently assigned requests, matching the existing screen's fields.
$script:svg.Add('<g id="recent_assignments">')
Text 280 1030 '최근 배정 이력' 23 '#1E2124' $true
Box 280 1079 1120 175 '#FFFFFF' '#CDD1D5' 8
Box 281 1080 1118 47 '#F0F3F6' '' 6
Text 304 1094 '청구인' 15 '#464C53' $true
Text 660 1094 '업무담당자' 15 '#464C53' $true
Text 906 1094 '배정시각' 15 '#464C53' $true
Text 1272 1094 '상태' 15 '#464C53' $true
Line 280 1127 1400 1127
Text 304 1146 '#99 박예시' 16 '#174D9D'
Text 660 1146 'staff4' 16 '#1E2124'
Text 906 1146 '2026.09.07 08:50' 16 '#464C53'
Box 1257 1139 78 31 '#ECF2FE' '' 4
Text 1273 1145 '판단중' 14 '#174D9D'
Line 280 1190 1400 1190
Text 304 1208 '#98 최예시' 16 '#174D9D'
Text 660 1208 'staff7' 16 '#1E2124'
Text 906 1208 '2026.09.06 16:30' 16 '#464C53'
Box 1257 1201 78 31 '#E7F4EF' '' 4
Text 1282 1207 '완료' 14 '#187348'
$script:svg.Add('</g>')
Text 280 1296 '© 2026 한국전력공사' 13 '#6D7882'

$script:svg.Add('</svg>')
$svgPath = Join-Path $outputDir 'krds-dispatch-draft.svg'
$pngPath = Join-Path $outputDir 'krds-dispatch-draft.png'
[System.IO.File]::WriteAllLines($svgPath, $script:svg, [System.Text.UTF8Encoding]::new($false))
$script:bitmap.Save($pngPath, [System.Drawing.Imaging.ImageFormat]::Png)
$script:format.Dispose()
$script:fontFamily.Dispose()
$script:graphics.Dispose()
$script:bitmap.Dispose()
Write-Output "SVG: $svgPath"
Write-Output "Preview: $pngPath"
