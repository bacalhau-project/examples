# Random Helper Scripts

## Enable Tests on All Cells in All Notebooks

```bash
find . -type f -iname "*.ipynb" -exec ./ops/enable_execution.sh {} \; 
```

## Disable Tests on All Cells in All Notebooks

```bash
find . -type f -iname "*.ipynb" -exec ./ops/disable_execution.sh {} \; 
```