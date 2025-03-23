# Enhanced Invoice Processing System

A comprehensive Python-based system for processing supplier invoices, extracting detailed line-item data, and analyzing pricing trends. Designed specifically for electrical contracting businesses.

## Features

### Basic Invoice Processing
- Extract summary data from PDF invoices (date, job name, supplier, total cost)
- Handle different vendor formats through vendor-specific templates
- Organize invoice data into Excel sheets by date
- Auto-format Excel output with proper formatting and calculations
- Download invoice attachments from Yahoo Mail
- Interactive training mode for new vendor formats

### Enhanced Line Item Extraction
- Extract detailed line-item data including part numbers, descriptions, and prices
- Build a comprehensive historical database of part pricing
- Support for both table-based and pattern-based extraction methods
- Customizable descriptions for parts
- SQLite database backend for efficient storage and retrieval

### Price Analysis with Local LLM
- Integration with local LLM models via API, command-line, or llama.cpp
- Automatic analysis of price trends and vendor comparisons
- Identification of significant price changes
- Recommendations for optimal vendor selection
- Customizable analysis prompts

### Automation
- Scheduled email fetching and processing
- Silent mode for background operation
- Comprehensive logging

## Installation

1. Clone or download this repository to your local machine
2. Install Python 3.8 or higher if not already installed
3. Install required packages:

```bash
pip install -r requirements.txt
```

4. Set up a local LLM (optional, for price analysis features):
   - Install a text-generation API server like oobabooga/text-generation-webui
   - Or set up llama.cpp with a suitable model
   - Configure the LLM settings in llm_config.json

## Usage

### Training Mode

Before using the system, you need to train it to recognize your vendor invoice formats:

```bash
python main.py --train --vendor "Supplier Name"
```

Follow the interactive prompts to identify different fields in the sample invoice, including both summary fields and line item tables.

### Processing Invoices

Process invoices with one of these commands:

```bash
# Process a single PDF
python main.py --pdf path/to/invoice.pdf

# Process all PDFs in a folder
python main.py --folder path/to/invoice/folder

# Fetch from email and process
python main.py --email
```

### Processing Modes

You can choose to extract summary data, line items, or both:

```bash
# Extract only summary data
python main.py --pdf invoice.pdf --mode summary

# Extract only line items
python main.py --pdf invoice.pdf --mode items

# Extract both (default)
python main.py --pdf invoice.pdf --mode full
```

### LLM Analysis

Run analysis on the price data:

```bash
# Process invoice and run analysis
python main.py --pdf invoice.pdf --analyze

# Only run analysis on existing data
python main.py --analyze
```