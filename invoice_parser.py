#!/usr/bin/env python3
"""
Invoice Parser Module
--------------------
Extracts structured data from invoice PDFs using vendor-specific templates.
Handles both summary invoice data and detailed line-item extraction.
"""

import re
import os
import logging
from datetime import datetime
import pdfplumber
from vendor_config import VendorConfig

logger = logging.getLogger(__name__)

class InvoiceParser:
    def __init__(self, vendor_config):
        """
        Initialize the invoice parser with vendor configurations.
        
        Args:
            vendor_config: VendorConfig object containing vendor-specific parsing rules
        """
        self.vendor_config = vendor_config
        self.default_date_format = "%m/%d/%Y"
    
    def extract_from_pdf(self, pdf_path):
        """
        Extract invoice data from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of dictionaries containing invoice data
        """
        # Determine the vendor based on the PDF content
        vendor_name = self.identify_vendor(pdf_path)
        if not vendor_name:
            logger.warning(f"Unknown vendor format for {pdf_path}")
            return []
            
        logger.info(f"Identified vendor: {vendor_name}")
        
        # Get vendor-specific extraction rules
        vendor_rules = self.vendor_config.get_vendor_rules(vendor_name)
        if not vendor_rules:
            logger.warning(f"No rules found for vendor: {vendor_name}")
            return []
            
        # Extract text from PDF
        text_content = self._extract_pdf_text(pdf_path)
        
        # Some vendors may have multiple invoices in one PDF
        if vendor_rules.get('multiple_invoices', False):
            # Split the text into sections for each invoice
            invoice_sections = self._split_multiple_invoices(text_content, vendor_rules)
            return [self._extract_invoice_data(section, vendor_rules) for section in invoice_sections]
        else:
            # Single invoice in the PDF
            return [self._extract_invoice_data(text_content, vendor_rules)]

    def identify_vendor(self, pdf_path):
        """
        Identify the vendor based on PDF content.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Vendor name if identified, None otherwise
        """
        # Extract first page text for identification
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) > 0:
                    first_page_text = pdf.pages[0].extract_text()
                else:
                    return None
            
            # Try to match against known vendor identifiers
            for vendor, rules in self.vendor_config.vendors.items():
                identifier = rules.get('identifier', '')
                if identifier and identifier in first_page_text:
                    return vendor
        except Exception as e:
            logger.error(f"Error identifying vendor for {pdf_path}: {str(e)}")
                
        return None
    
    def _extract_pdf_text(self, pdf_path):
        """
        Extract all text content from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            String containing all text from the PDF
        """
        full_text = ""
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                full_text += page.extract_text() + "\n\n"
                
        return full_text
    
    def _split_multiple_invoices(self, text_content, vendor_rules):
        """
        Split text content into separate invoice sections for vendors with multiple invoices per PDF.
        
        Args:
            text_content: Full text content of the PDF
            vendor_rules: Rules specific to this vendor
            
        Returns:
            List of text sections, one per invoice
        """
        separator = vendor_rules.get('invoice_separator', '')
        if not separator:
            # Default to treating the whole document as one invoice
            return [text_content]
            
        # Split by the separator pattern
        sections = re.split(separator, text_content)
        
        # Filter out empty sections
        return [section.strip() for section in sections if section.strip()]
    
    def _extract_invoice_data(self, text_content, vendor_rules):
        """
        Extract structured data from a single invoice using vendor-specific rules.
        
        Args:
            text_content: Text content for a single invoice
            vendor_rules: Rules specific to this vendor
            
        Returns:
            Dictionary with extracted invoice data
        """
        invoice_data = {
            'date': None,
            'job_name': '',
            'supply_house': vendor_rules.get('name', 'Unknown Vendor'),
            'total_cost': 0.0,
            'job_cost': 0.0,  # Will be set later based on user input
            'invoice_number': '',
            'processed_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Extract date
        date_pattern = vendor_rules.get('date_pattern', '')
        if date_pattern:
            date_match = re.search(date_pattern, text_content)
            if date_match:
                date_str = date_match.group(1)
                date_format = vendor_rules.get('date_format', self.default_date_format)
                try:
                    invoice_data['date'] = datetime.strptime(date_str, date_format).strftime('%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Could not parse date: {date_str}")
        
        # Extract job name
        job_pattern = vendor_rules.get('job_name_pattern', '')
        if job_pattern:
            job_match = re.search(job_pattern, text_content)
            if job_match:
                invoice_data['job_name'] = job_match.group(1).strip()
        
        # Extract total cost
        total_pattern = vendor_rules.get('total_cost_pattern', '')
        if total_pattern:
            total_match = re.search(total_pattern, text_content)
            if total_match:
                # Remove any non-numeric characters except decimal point
                cost_str = re.sub(r'[^\d.]', '', total_match.group(1))
                try:
                    invoice_data['total_cost'] = float(cost_str)
                except ValueError:
                    logger.warning(f"Could not parse total cost: {total_match.group(1)}")
        
        # Extract invoice number
        invoice_num_pattern = vendor_rules.get('invoice_number_pattern', '')
        if invoice_num_pattern:
            invoice_match = re.search(invoice_num_pattern, text_content)
            if invoice_match:
                invoice_data['invoice_number'] = invoice_match.group(1).strip()
        
        return invoice_data
    
    def extract_line_items(self, pdf_path, vendor_name):
        """
        Extract individual line items from an invoice PDF.
        
        Args:
            pdf_path: Path to the PDF file
            vendor_name: Name of the vendor
            
        Returns:
            List of dictionaries containing line item data
        """
        # Get vendor-specific line item extraction rules
        vendor_rules = self.vendor_config.get_vendor_rules(vendor_name)
        if not vendor_rules or 'line_item_config' not in vendor_rules:
            logger.warning(f"No line item extraction rules found for vendor: {vendor_name}")
            return []
        
        line_item_config = vendor_rules['line_item_config']
        extraction_method = line_item_config.get('extraction_method', 'table')
        
        # Extract based on configured method
        if extraction_method == 'table':
            return self._extract_line_items_from_tables(pdf_path, line_item_config)
        elif extraction_method == 'pattern':
            return self._extract_line_items_from_patterns(pdf_path, line_item_config)
        else:
            logger.warning(f"Unknown extraction method: {extraction_method}")
            return []
    
    def _extract_line_items_from_tables(self, pdf_path, line_item_config):
        """
        Extract line items from tables in the PDF.
        
        Args:
            pdf_path: Path to the PDF file
            line_item_config: Configuration for line item extraction
            
        Returns:
            List of dictionaries containing line item data
        """
        items = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Get invoice date and number for reference
                invoice_data = self.extract_from_pdf(pdf_path)
                if not invoice_data:
                    return []
                
                invoice_date = invoice_data[0].get('date')
                invoice_number = invoice_data[0].get('invoice_number')
                vendor_name = invoice_data[0].get('supply_house')
                
                # Find tables in each page
                for page_num, page in enumerate(pdf.pages):
                    # Set table extraction settings
                    table_settings = line_item_config.get('table_settings', {})
                    
                    # Extract tables
                    tables = page.extract_tables(**table_settings)
                    
                    for table in tables:
                        # Skip if not a valid line item table
                        if not self._is_line_item_table(table, line_item_config):
                            continue
                        
                        # Extract header row if needed
                        header_row = None
                        if line_item_config.get('has_header', True):
                            header_row = table[0]
                            table = table[1:]
                        
                        # Process each row in table
                        for row in table:
                            item = self._parse_item_row(row, header_row, line_item_config)
                            
                            if item:
                                # Add invoice reference information
                                item['date'] = invoice_date
                                item['invoice_number'] = invoice_number
                                item['vendor'] = vendor_name
                                items.append(item)
                                
        except Exception as e:
            logger.error(f"Error extracting line items from {pdf_path}: {str(e)}", exc_info=True)
        
        return items
    
    def _is_line_item_table(self, table, line_item_config):
        """
        Check if a table contains line items.
        
        Args:
            table: Table data from pdfplumber
            line_item_config: Configuration for line item extraction
            
        Returns:
            Boolean indicating if this is a line item table
        """
        if not table or len(table) < 2:  # Need at least header and one row
            return False
        
        # Check for required columns in header or specific pattern
        identifier_text = line_item_config.get('table_identifier', '')
        if identifier_text:
            # Check if identifier text is in any cell
            return any(any(cell and identifier_text in str(cell) for cell in row) 
                       for row in table[:min(3, len(table))])  # Check first few rows
        
        # Otherwise check for expected number of columns
        min_columns = line_item_config.get('min_columns', 3)
        return any(len([c for c in row if c]) >= min_columns for row in table[:min(3, len(table))])
    
    def _parse_item_row(self, row, header_row, line_item_config):
        """
        Parse a row from a table into a line item.
        
        Args:
            row: Row data from table
            header_row: Header row data (or None)
            line_item_config: Configuration for line item extraction
            
        Returns:
            Dictionary with line item data or None if invalid
        """
        # Skip empty or invalid rows
        if not row or all(cell is None or cell.strip() == '' for cell in row):
            return None
        
        # Map columns based on configuration or header
        column_map = line_item_config.get('column_map', {})
        
        # Prepare item data
        item = {
            'part_number': '',
            'original_description': '',
            'custom_description': '',  # Will be filled in by user or copied from original
            'quantity': 1,
            'unit_price': 0.0,
            'total_price': 0.0
        }
        
        # Extract values based on column mapping
        for field, col_index in column_map.items():
            if col_index < len(row) and row[col_index] is not None:
                value = str(row[col_index]).strip()
                
                # Handle numeric fields
                if field in ['quantity', 'unit_price', 'total_price']:
                    try:
                        # Remove any non-numeric characters except decimal point
                        clean_value = re.sub(r'[^\d.]', '', value)
                        if clean_value:
                            item[field] = float(clean_value)
                    except ValueError:
                        pass
                else:
                    item[field] = value
        
        # If no custom description set, use original for now
        if not item['custom_description'] and item['original_description']:
            item['custom_description'] = item['original_description']
        
        # Validate the item - require at least part number or description and some price info
        has_identifier = item['part_number'] or item['original_description']
        has_price = item['unit_price'] > 0 or item['total_price'] > 0
        
        if has_identifier and has_price:
            return item
        
        return None
    
    def _extract_line_items_from_patterns(self, pdf_path, line_item_config):
        """
        Extract line items using regex patterns.
        
        Args:
            pdf_path: Path to the PDF file
            line_item_config: Configuration for line item extraction
            
        Returns:
            List of dictionaries containing line item data
        """
        items = []
        
        try:
            # Get text content
            text_content = self._extract_pdf_text(pdf_path)
            
            # Get invoice info for reference
            invoice_data = self.extract_from_pdf(pdf_path)
            if not invoice_data:
                return []
            
            invoice_date = invoice_data[0].get('date')
            invoice_number = invoice_data[0].get('invoice_number')
            vendor_name = invoice_data[0].get('supply_house')
            
            # Get item pattern
            item_pattern = line_item_config.get('item_pattern', '')
            if not item_pattern:
                logger.warning("No item pattern defined for pattern-based extraction")
                return []
            
            # Find all items using the pattern
            for match in re.finditer(item_pattern, text_content, re.MULTILINE):
                try:
                    # Extract fields based on named capture groups
                    item = {
                        'part_number': match.group('part_number') if 'part_number' in match.groupdict() else '',
                        'original_description': match.group('description') if 'description' in match.groupdict() else '',
                        'custom_description': '',  # Will be filled in later
                        'quantity': 1,
                        'unit_price': 0.0,
                        'total_price': 0.0,
                        'date': invoice_date,
                        'invoice_number': invoice_number,
                        'vendor': vendor_name
                    }
                    
                    # Handle numeric fields
                    if 'quantity' in match.groupdict():
                        try:
                            item['quantity'] = float(re.sub(r'[^\d.]', '', match.group('quantity')))
                        except ValueError:
                            pass
                    
                    if 'unit_price' in match.groupdict():
                        try:
                            item['unit_price'] = float(re.sub(r'[^\d.]', '', match.group('unit_price')))
                        except ValueError:
                            pass
                    
                    if 'total_price' in match.groupdict():
                        try:
                            item['total_price'] = float(re.sub(r'[^\d.]', '', match.group('total_price')))
                        except ValueError:
                            pass
                    
                    # If no custom description set, use original
                    if not item['custom_description'] and item['original_description']:
                        item['custom_description'] = item['original_description']
                    
                    # Add item if it has minimum required info
                    if (item['part_number'] or item['original_description']) and (item['unit_price'] > 0 or item['total_price'] > 0):
                        items.append(item)
                        
                except Exception as e:
                    logger.warning(f"Error parsing line item: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error extracting line items from {pdf_path}: {str(e)}", exc_info=True)
            
        return items
    
    def extract_training_page(self, pdf_path):
        """
        Extract the first page text from a PDF for training purposes.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Text content of the first page
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) > 0:
                    return pdf.pages[0].extract_text()
                else:
                    return "Empty PDF file"
        except Exception as e:
            return f"Error extracting text: {str(e)}"
    
    def extract_sample_tables(self, pdf_path, page_num=0):
        """
        Extract tables from a sample PDF page for training purposes.
        
        Args:
            pdf_path: Path to the PDF file
            page_num: Page number to extract from (0-based)
            
        Returns:
            List of tables found on the page
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if page_num < len(pdf.pages):
                    page = pdf.pages[page_num]
                    return page.extract_tables()
                else:
                    return []
        except Exception as e:
            logger.error(f"Error extracting tables: {str(e)}")
            return []