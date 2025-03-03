#!/bin/sh

print_usage() {
    echo "Usage: $0 [OPTIONS] PATH"
    echo "  PATH: file or directory to process"
    echo "Options:"
    echo "  --limit N: show only top N results"
    echo "  --format FORMAT: output format (text, json, or csv, default: text)"
    echo "  --output-file FILE: write results to FILE instead of stdout"
    exit 1
}

# Parse arguments
LIMIT=""
PATH_TO_PROCESS=""
OUTPUT_FILE=""
FORMAT="text"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --limit)
            if [ -z "$2" ] || ! [ "$2" -eq "$2" ] 2>/dev/null; then
                echo "Error: --limit requires a number"
                exit 1
            fi
            LIMIT="$2"
            shift 2
            ;;
        --format)
            if [ -z "$2" ]; then
                echo "Error: --format requires a value (json, csv, or text)"
                exit 1
            fi
            case "$2" in
                json|csv|text)
                    FORMAT="$2"
                    ;;
                *)
                    echo "Error: Invalid format '$2'. Must be json, csv, or text."
                    exit 1
                    ;;
            esac
            shift 2
            ;;
        --output-file)
            if [ -z "$2" ]; then
                echo "Error: --output-file requires a filename"
                exit 1
            fi
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --help)
            print_usage
            ;;
        -*)
            echo "Error: Unknown option $1"
            print_usage
            ;;
        *)
            if [ -z "$PATH_TO_PROCESS" ]; then
                PATH_TO_PROCESS="$1"
                shift
            else
                echo "Error: Too many arguments"
                print_usage
            fi
            ;;
    esac
done

if [ -z "$PATH_TO_PROCESS" ]; then
    echo "Error: No path specified"
    print_usage
fi

# Function to process content and return word counts
process_content() {
    # First convert to lowercase
    tr '[:upper:]' '[:lower:]' | \
    # Replace all non-alphanumeric chars with spaces (including newlines)
    tr -cs '[:alnum:]' ' ' | \
    # Convert multiple spaces to single space
    tr -s ' ' | \
    # Split into words (one per line)
    tr ' ' '\n' | \
    # Remove empty lines
    grep -v '^$' | \
    # Sort and count unique occurrences
    sort | \
    uniq -c | \
    # Sort by count (descending) and alphabetically
    sort -rn | \
    # Apply limit if specified
    if [ -n "$LIMIT" ]; then
        head -n "$LIMIT"
    else
        cat
    fi
}

# Function to format output as text
format_as_text() {
    awk '{printf "%-30s %s\n", $2, $1}'
}

# Function to format output as CSV
format_as_csv() {
    echo "word,count"
    awk '{printf "%s,%s\n", $2, $1}'
}

# Function to format output as JSON
format_as_json() {
    echo "["
    awk 'BEGIN {first=1} {
        if (!first) printf ",\n";
        printf "  {\"word\": \"%s\", \"count\": %s}", $2, $1;
        first=0;
    }'
    echo ""
    echo "]"
}

# Check if path exists
if [ ! -e "$PATH_TO_PROCESS" ]; then
    echo "Error: '$PATH_TO_PROCESS' does not exist!"
    exit 1
fi

# Process the content
if [ -f "$PATH_TO_PROCESS" ]; then
    # Process single file
    WORD_COUNTS=$(cat "$PATH_TO_PROCESS" | process_content)
elif [ -d "$PATH_TO_PROCESS" ]; then
    # Process directory recursively
    WORD_COUNTS=$(find "$PATH_TO_PROCESS" -type f -exec cat {} + | process_content)
else
    echo "Error: '$PATH_TO_PROCESS' is neither a file nor a directory!"
    exit 1
fi

# Get total word count and unique word count
TOTAL_WORDS=$(echo "$WORD_COUNTS" | awk '{sum += $1} END {print sum}')
UNIQUE_WORDS=$(echo "$WORD_COUNTS" | wc -l)

# Print summary to stdout
echo "Word Count Summary:"
echo "----------------------------------------"
echo "Path processed: $PATH_TO_PROCESS"
echo "Total words: $TOTAL_WORDS"
echo "Unique words: $UNIQUE_WORDS"
if [ -n "$LIMIT" ]; then
    echo "Showing top $LIMIT words"
fi
echo "----------------------------------------"
echo "Top 5 words:"
echo "$WORD_COUNTS" | head -n 5 | format_as_text
echo "----------------------------------------"

# Handle results output
if [ -n "$OUTPUT_FILE" ]; then
    echo "Full results written to $OUTPUT_FILE (format: $FORMAT)"
    
    # Write to output file
    case "$FORMAT" in
        json)
            echo "$WORD_COUNTS" | format_as_json > "$OUTPUT_FILE"
            ;;
        csv)
            echo "$WORD_COUNTS" | format_as_csv > "$OUTPUT_FILE"
            ;;
        text|*)
            {
                echo "Word count results:"
                echo "----------------------------------------"
                echo "Word                           Count"
                echo "----------------------------------------"
                echo "$WORD_COUNTS" | format_as_text
            } > "$OUTPUT_FILE"
            ;;
    esac
else
    # Display full results to stdout
    echo "Full results:"
    echo "----------------------------------------"
    echo "Word                           Count"
    echo "----------------------------------------"
    echo "$WORD_COUNTS" | format_as_text
fi 