# Attempts to download all of the necessary tools to build 
# the demo

function Add-Path($Path) {
    $Path = [Environment]::GetEnvironmentVariable("PATH", "Machine") + [IO.Path]::PathSeparator + $Path
    [Environment]::SetEnvironmentVariable( "Path", $Path, "Machine" )
}

# First up, golang.
Invoke-WebRequest -Uri "https://go.dev/dl/go1.20.11.windows-amd64.msi" -OutFile "C:\Users\mycelial\go1.20.11.windows-amd64.msi"


# Service manager 
Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "C:\Users\mycelial\nssm-2.24.zip"
Expand-Archive -LiteralPath 'C:\Users\mycelial\nssm-2.24.zip' -DestinationPath C:\Users\mycelial\

# Rust/Cargo 
Invoke-WebRequest -Uri "https://static.rust-lang.org/rustup/dist/i686-pc-windows-gnu/rustup-init.exe" -OutFile "C:\Users\mycelial\rustup-init.exe"
# set PATH=%PATH%;/Users/mycelial/.cargo/bin

# Github client for build 
Invoke-WebRequest -Uri "https://central.github.com/deployments/desktop/desktop/latest/win32" -OutFile "github-install.exe"
github-install.exe 
