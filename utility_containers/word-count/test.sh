#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if the image already exists, build only if it doesn't
if ! docker image inspect word-count &>/dev/null; then
    echo -e "${YELLOW}Building word-count container...${NC}"
    docker build -t word-count .
else
    echo -e "${YELLOW}Using existing word-count container...${NC}"
fi

# Create test directory and sample files
echo -e "${YELLOW}Creating test files...${NC}"
mkdir -p test_data
echo "hello world hello test container word count test" > test_data/sample1.txt
echo "hello world again this is another test file for word counting" > test_data/sample2.txt

# Test 1: Basic word count on a single file
echo -e "${YELLOW}Test 1: Basic word count on a single file${NC}"
docker run -v $(pwd)/test_data:/data word-count /data/sample1.txt
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test 1 passed${NC}"
else
    echo -e "${RED}✗ Test 1 failed${NC}"
    exit 1
fi

# Test 2: Word count with limit
echo -e "\n${YELLOW}Test 2: Word count with limit${NC}"
docker run -v $(pwd)/test_data:/data word-count --limit 3 /data/sample1.txt
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test 2 passed${NC}"
else
    echo -e "${RED}✗ Test 2 failed${NC}"
    exit 1
fi

# Test 3: Word count on directory
echo -e "\n${YELLOW}Test 3: Word count on directory${NC}"
docker run -v $(pwd)/test_data:/data word-count /data
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test 3 passed${NC}"
else
    echo -e "${RED}✗ Test 3 failed${NC}"
    exit 1
fi

# Test 4: Output to file
echo -e "\n${YELLOW}Test 4: Output to file${NC}"
docker run -v $(pwd)/test_data:/data word-count --output-file /data/results.txt /data/sample1.txt
if [ $? -eq 0 ] && [ -f "test_data/results.txt" ]; then
    echo -e "${GREEN}✓ Test 4 passed${NC}"
    echo "Output file contents:"
    cat test_data/results.txt
else
    echo -e "${RED}✗ Test 4 failed${NC}"
    exit 1
fi

# Test 5: JSON output
echo -e "\n${YELLOW}Test 5: JSON output${NC}"
docker run -v $(pwd)/test_data:/data word-count --format json --output-file /data/results.json /data/sample1.txt
if [ $? -eq 0 ] && [ -f "test_data/results.json" ]; then
    echo -e "${GREEN}✓ Test 5 passed${NC}"
    echo "JSON output:"
    cat test_data/results.json
else
    echo -e "${RED}✗ Test 5 failed${NC}"
    exit 1
fi

# Test 6: CSV output
echo -e "\n${YELLOW}Test 6: CSV output${NC}"
docker run -v $(pwd)/test_data:/data word-count --format csv --output-file /data/results.csv /data/sample1.txt
if [ $? -eq 0 ] && [ -f "test_data/results.csv" ]; then
    echo -e "${GREEN}✓ Test 6 passed${NC}"
    echo "CSV output:"
    cat test_data/results.csv
else
    echo -e "${RED}✗ Test 6 failed${NC}"
    exit 1
fi

# Test 7: Check Docker labels
echo -e "\n${YELLOW}Test 7: Checking Docker labels${NC}"
LABELS=$(docker inspect word-count | grep -A 20 "Labels")
if [[ $LABELS == *"org.opencontainers.image.title"* ]] && [[ $LABELS == *"bacalhau.org"* ]]; then
    echo -e "${GREEN}✓ Test 7 passed${NC}"
    echo "Docker labels found:"
    echo "$LABELS"
else
    echo -e "${RED}✗ Test 7 failed${NC}"
    echo "Docker labels not found or incomplete"
    exit 1
fi

# Test 8: Real-world test with Project Gutenberg book
echo -e "\n${YELLOW}Test 8: Processing a book from Project Gutenberg${NC}"
# Download a small book from Project Gutenberg
echo "Downloading 'The Art of War' by Sun Tzu from Project Gutenberg..."
curl -s https://www.gutenberg.org/files/132/132-0.txt > test_data/art-of-war.txt

# Process the book and get top 20 words
echo "Processing 'The Art of War' with word-count container..."
docker run -v $(pwd)/test_data:/data word-count --limit 20 --format json --output-file /data/art-of-war-results.json /data/art-of-war.txt

if [ $? -eq 0 ] && [ -f "test_data/art-of-war-results.json" ]; then
    echo -e "${GREEN}✓ Test 8 passed${NC}"
    echo "Top 20 words in 'The Art of War':"
    cat test_data/art-of-war-results.json
else
    echo -e "${RED}✗ Test 8 failed${NC}"
    exit 1
fi

# Don't clean up if running from make test (it will handle cleanup)
if [[ "$1" != "--no-cleanup" ]]; then
    echo -e "\n${YELLOW}Cleaning up test files...${NC}"
    rm -rf test_data
fi

echo -e "\n${GREEN}All tests passed successfully!${NC}"
echo "The word-count container is ready for use with Bacalhau." 