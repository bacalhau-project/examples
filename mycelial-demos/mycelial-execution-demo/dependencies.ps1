# Attempts to download all of the necessary tools to build 
# the demo

# Windows build tools
Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vc_redist.x64.exe"  -OutFile "vc_redist.x64.exe"
Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vs_BuildTools.exe" -OutFile "vs_BuildTools.exe"
./vc_redist.x64.exe
./vs_BuildTools.exe 


# First up, golang.
Invoke-WebRequest -Uri "https://go.dev/dl/go1.20.11.windows-amd64.msi" -OutFile "go1.20.11.windows-amd64.msi"

# Nodejs
Invoke-WebRequest -Uri "https://nodejs.org/dist/v20.9.0/node-v20.9.0-x64.msi" -OutFile "node-v20.9.0-x64.msi"

# Service manager 
Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "nssm-2.24.zip"
Expand-Archive -LiteralPath 'C:\Users\mycelial\nssm-2.24.zip' -DestinationPath C:\Users\mycelial\

# Rust/Cargo 
Invoke-WebRequest -Uri "https://static.rust-lang.org/rustup/dist/i686-pc-windows-gnu/rustup-init.exe" -OutFile "rustup-init.exe"
# set PATH=%PATH%;/Users/USERNAME/.cargo/bin

# Github client for build 
Invoke-WebRequest -Uri "https://central.github.com/deployments/desktop/desktop/latest/win32" -OutFile "github-install.exe"
github-install.exe 
