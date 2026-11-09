# 把机器人小号的 QQ 密码存成本机 DPAPI 密文（给 guard_once.ps1 做密码登录用）
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\napcat\set-qq-password.ps1 -NapCatDir D:\NapCat
#
# 安全说明：
#   - 密文用 Windows DPAPI（当前用户作用域）加密，换用户、换机器都解不开；
#   - 文件落在 <NapCatDir>\secrets\qq_pwd.dpapi，已在 .gitignore 里，不要提交；
#   - 仍然只用小号：密码登录同样属于第三方客户端，违反协议的风险不变。

param(
    [string]$NapCatDir = 'D:\NapCat'
)

$dir = Join-Path $NapCatDir 'secrets'
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$target = Join-Path $dir 'qq_pwd.dpapi'

if (Test-Path $target) {
    $ans = Read-Host '已经有密码密文了，要覆盖吗？(y/N)'
    if ($ans -notmatch '^[yY]') { Write-Host '没改。'; exit 0 }
}

$sec = Read-Host '机器人小号的 QQ 密码（输入不回显）' -AsSecureString
if (-not $sec) { Write-Error '没输入密码'; exit 1 }

$enc = ConvertFrom-SecureString $sec
[System.IO.File]::WriteAllText($target, $enc, [System.Text.UTF8Encoding]::new($false))

# 立刻回读验证一次，避免存进去解不开
$back = ConvertTo-SecureString ((Get-Content $target -Raw).Trim())
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($back)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    Write-Host ("已保存：" + $target + "（长度 " + $plain.Length + "，只有当前 Windows 用户能解）")
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
