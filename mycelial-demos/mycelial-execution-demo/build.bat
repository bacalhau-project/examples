:: Steps to build the necessary tools for this demo on Windows
:: After checking the required dependencies are installed, it 
:: will attempt to build the relevant branches of bacalhau and 
:: mycelial.

:: Required tool check ...
where /q git || ECHO Could not find git and it is required. && EXIT /B
where /q cargo || ECHO Could not find rust and it is required. && EXIT /B
where /q go || ECHO Could not find go and it is required. && EXIT /B
where /q gmake || ECHO Could not find gmake and it is required. && EXIT /B


:: Fetch bacalhau code 
cd build 
git clone https://github.com/bacalhau-project/bacalhau.git
cd bacalhau
git checkout process-executor 
make build 
cp bin/windows/bacalhau.exe ../../bin
cd ..

:: Fetch and build mycelial
git clone https://github.com/rossjones/mycelial.git
cd mycelial
git checkout bacalhau-node
cargo build --release 
cp target/release/myceliald.exe ../../bin 
cp target/release/server.exe ../../bin/mycelial-server.exe 
cd ..
