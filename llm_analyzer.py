#!/usr/bin/env python3
"""
LLM Analyzer Module
-----------------
Interfaces with a local LLM to analyze invoice item data.
"""

import os
import json
import logging
import requests
import tempfile
from datetime import datetime
import subprocess
import shutil

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    def __init__(self, item_database, config_path="llm_config.json"):
        """
        Initialize the LLM analyzer.
        
        Args:
            item_database: ItemDatabase object to analyze
            config_path: Path to the LLM configuration file
        """
        self.item_db = item_database
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self):
        """
        Load LLM configuration from file or create default.
        
        Returns:
            Dictionary with LLM configuration
        """
        default_config = {
            'llm_type': 'api',  # Options: 'api', 'command', 'llama.cpp'
            'api_url': 'http://localhost:5000/api/generate',  # For API-based LLMs
            'command': '',  # For command-line based LLMs
            'model_path': '',  # For llama.cpp style models
            'prompt_template': "Analyze the following electrical supply item data:\n\n{data}\n\nPlease provide the following analysis:\n1. Identify any significant price changes\n2. Compare prices across vendors for the same items\n3. Identify items with unusual pricing\n4. Suggest potential cost-saving opportunities\n\nAnalysis:",
            'output_format': 'text'  # Options: 'text', 'json'
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    # Update default with loaded values
                    for key, value in loaded_config.items():
                        default_config[key] = value
                    return default_config
            except Exception as e:
                logger.error(f"Error loading LLM config: {str(e)}")
                return default_config
        else:
            # Save the default config
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(default_config, f, indent=4)
            except Exception as e:
                logger.error(f"Error saving default LLM config: {str(e)}")
            
            return default_config
    
    def analyze_recent_data(self, days=30):
        """
        Analyze recent invoice data.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Analysis results from the LLM
        """
        try:
            # Get recent data
            recent_items = self.item_db.get_recent_items(days)
            
            if not recent_items:
                return "No recent data available for analysis."
            
            # Get price changes
            price_changes = self.item_db.find_price_changes(threshold_percent=3, days=days)
            
            # Prepare data for LLM
            analysis_data = {
                'recent_items': recent_items,
                'price_changes': price_changes,
                'days_analyzed': days,
                'total_items': len(recent_items),
                'unique_parts': len(set(item.get('part_number', '') for item in recent_items)),
                'vendors': list(set(item.get('vendor', '') for item in recent_items))
            }
            
            # Export for LLM
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp:
                json.dump(analysis_data, tmp, indent=2)
                tmp_path = tmp.name
            
            # Run analysis
            results = self._run_llm_analysis(tmp_path)
            
            # Clean up
            try:
                os.unlink(tmp_path)
            except:
                pass
                
            return results
        except Exception as e:
            logger.error(f"Error running recent data analysis: {str(e)}", exc_info=True)
            return f"Error during analysis: {str(e)}"
    
    def analyze_specific_vendors(self, vendors, days=90):
        """
        Compare pricing across specific vendors.
        
        Args:
            vendors: List of vendor names to compare
            days: Number of days to analyze
            
        Returns:
            Analysis results from the LLM
        """
        try:
            vendor_data = {}
            
            for vendor in vendors:
                vendor_items = self.item_db.get_items_by_vendor(vendor)
                vendor_data[vendor] = vendor_items
            
            # Find common parts
            part_sets = []
            for vendor, items in vendor_data.items():
                part_sets.append(set(item.get('part_number', '') for item in items if item.get('part_number', '')))
            
            if not part_sets:
                return "No data available for the specified vendors."
                
            common_parts = set.intersection(*part_sets) if part_sets else set()
            
            # Prepare comparison data
            comparison_data = {
                'vendors': vendors,
                'common_parts': list(common_parts),
                'vendor_items': vendor_data,
                'days_analyzed': days
            }
            
            # Export for LLM
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp:
                json.dump(comparison_data, tmp, indent=2)
                tmp_path = tmp.name
            
            # Set specific prompt for vendor comparison
            custom_prompt = f"Analyze the following electrical supply pricing data across vendors: {', '.join(vendors)}.\n\n{{data}}\n\nPlease provide:\n1. Price comparison for common items across these vendors\n2. Identify which vendor offers the best price for each item\n3. Overall assessment of which vendor is most cost-effective\n4. Recommendations for optimizing vendor selection\n\nAnalysis:"
            
            # Run analysis
            results = self._run_llm_analysis(tmp_path, prompt_override=custom_prompt)
            
            # Clean up
            try:
                os.unlink(tmp_path)
            except:
                pass
                
            return results
        except Exception as e:
            logger.error(f"Error running vendor comparison: {str(e)}", exc_info=True)
            return f"Error during vendor analysis: {str(e)}"
    
    def analyze_price_trends(self, part_numbers=None, days=180):
        """
        Analyze price trends for specific parts or all parts.
        
        Args:
            part_numbers: List of part numbers to analyze or None for all
            days: Number of days to analyze
            
        Returns:
            Analysis results from the LLM
        """
        try:
            # If no specific parts provided, get top parts by transaction count
            if not part_numbers:
                # Get all parts from recent data
                recent_items = self.item_db.get_recent_items(days)
                
                # Count occurrences of each part number
                part_counts = {}
                for item in recent_items:
                    part_num = item.get('part_number', '')
                    if part_num:
                        part_counts[part_num] = part_counts.get(part_num, 0) + 1
                
                # Get top 20 parts
                top_parts = sorted(part_counts.items(), key=lambda x: x[1], reverse=True)[:20]
                part_numbers = [p[0] for p in top_parts]
            
            if not part_numbers:
                return "No part data available for analysis."
            
            # Get price history for each part
            price_data = {}
            for part in part_numbers:
                price_data[part] = self.item_db.get_price_history(part)
            
            # Get additional context for parts
            part_info = {}
            for part in part_numbers:
                items = self.item_db.get_items_by_part_number(part)
                if items:
                    part_info[part] = {
                        'description': items[0].get('custom_description', '') or items[0].get('original_description', ''),
                        'vendors': list(set(item.get('vendor', '') for item in items))
                    }
            
            # Prepare data for LLM
            analysis_data = {
                'part_numbers': part_numbers,
                'price_data': price_data,
                'part_info': part_info,
                'days_analyzed': days
            }
            
            # Export for LLM
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp:
                json.dump(analysis_data, tmp, indent=2)
                tmp_path = tmp.name
            
            # Set specific prompt for price trend analysis
            custom_prompt = "Analyze the following electrical supply price trend data:\n\n{data}\n\nPlease provide:\n1. Price trends for each part over time\n2. Identify seasonal patterns if any\n3. Forecast likely future price movements\n4. Recommend optimal timing for purchases\n\nAnalysis:"
            
            # Run analysis
            results = self._run_llm_analysis(tmp_path, prompt_override=custom_prompt)
            
            # Clean up
            try:
                os.unlink(tmp_path)
            except:
                pass
                
            return results
        except Exception as e:
            logger.error(f"Error analyzing price trends: {str(e)}", exc_info=True)
            return f"Error during price trend analysis: {str(e)}"
    
    def _run_llm_analysis(self, data_path, prompt_override=None):
        """
        Run LLM analysis on the provided data.
        
        Args:
            data_path: Path to the data file
            prompt_override: Optional custom prompt template
            
        Returns:
            Analysis results from the LLM
        """
        try:
            # Read the data file
            with open(data_path, 'r') as f:
                data_json = f.read()
            
            # Get the appropriate prompt
            prompt_template = prompt_override if prompt_override else self.config['prompt_template']
            prompt = prompt_template.format(data=data_json)
            
            # Determine which method to use for the LLM
            llm_type = self.config['llm_type']
            
            if llm_type == 'api':
                return self._run_api_llm(prompt)
            elif llm_type == 'command':
                return self._run_command_llm(prompt)
            elif llm_type == 'llama.cpp':
                return self._run_llama_cpp(prompt)
            else:
                return f"Unsupported LLM type: {llm_type}"
        except Exception as e:
            logger.error(f"Error running LLM analysis: {str(e)}", exc_info=True)
            return f"Error running LLM analysis: {str(e)}"
    
    def _run_api_llm(self, prompt):
        """
        Run analysis using a REST API-based LLM.
        
        Args:
            prompt: Prompt to send to the LLM
            
        Returns:
            Analysis results from the LLM
        """
        try:
            api_url = self.config['api_url']
            
            # Prepare the request
            payload = {
                'prompt': prompt,
                'max_new_tokens': 2000,
                'temperature': 0.7,
                'do_sample': True
            }
            
            # Send the request
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            
            # Extract the text from the response (format varies by API)
            if 'choices' in result and len(result['choices']) > 0:
                # OpenAI-style API
                return result['choices'][0]['text']
            elif 'results' in result and len(result['results']) > 0:
                # Some local API servers
                return result['results'][0]['text']
            elif 'response' in result:
                # Simple API format
                return result['response']
            elif 'generated_text' in result:
                # Hugging Face style API
                return result['generated_text']
            else:
                # Just return the raw response as a fallback
                return str(result)
                
        except Exception as e:
            logger.error(f"Error using API-based LLM: {str(e)}", exc_info=True)
            return f"Error using LLM API: {str(e)}"
    
    def _run_command_llm(self, prompt):
        """
        Run analysis using a command-line LLM.
        
        Args:
            prompt: Prompt to send to the LLM
            
        Returns:
            Analysis results from the LLM
        """
        try:
            command = self.config['command']
            
            if not command:
                return "No command specified for command-line LLM."
            
            # Create a temporary file with the prompt
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tmp:
                tmp.write(prompt)
                tmp_path = tmp.name
            
            # Run the command with the prompt file
            full_command = command.replace('{prompt_file}', tmp_path)
            result = subprocess.run(full_command, shell=True, capture_output=True, text=True)
            
            # Clean up
            try:
                os.unlink(tmp_path)
            except:
                pass
            
            if result.returncode != 0:
                logger.error(f"Command failed with error: {result.stderr}")
                return f"Error running LLM command: {result.stderr}"
            
            return result.stdout
            
        except Exception as e:
            logger.error(f"Error using command-line LLM: {str(e)}", exc_info=True)
            return f"Error using command-line LLM: {str(e)}"
    
    def _run_llama_cpp(self, prompt):
        """
        Run analysis using the llama.cpp framework.
        
        Args:
            prompt: Prompt to send to the LLM
            
        Returns:
            Analysis results from the LLM
        """
        try:
            model_path = self.config.get('model_path', '')
            
            if not model_path or not os.path.exists(model_path):
                return "Model path not specified or doesn't exist for llama.cpp."
            
            # Check if llama.cpp binaries are available
            llama_cpp_path = shutil.which('llama-cli') or shutil.which('main')
            
            if not llama_cpp_path:
                return "llama.cpp executable not found in PATH."
            
            # Create a temporary file with the prompt
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tmp:
                tmp.write(prompt)
                prompt_path = tmp.name
            
            # Create a temporary file for output
            output_path = tempfile.mktemp(suffix='.txt')
            
            # Run llama.cpp
            cmd = [
                llama_cpp_path,
                '-m', model_path,
                '-f', prompt_path,
                '-n', '2048',  # Number of tokens to predict
                '-t', '8',     # Number of threads
                '--temp', '0.7',
                '-o', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Read the output
            output = ""
            if os.path.exists(output_path):
                with open(output_path, 'r') as f:
                    output = f.read()
            
            # Clean up
            try:
                os.unlink(prompt_path)
                os.unlink(output_path)
            except:
                pass
            
            if result.returncode != 0:
                logger.error(f"llama.cpp failed with error: {result.stderr}")
                return f"Error running llama.cpp: {result.stderr}"
            
            return output
            
        except Exception as e:
            logger.error(f"Error using llama.cpp: {str(e)}", exc_info=True)
            return f"Error using llama.cpp: {str(e)}"
    
    def configure_llm(self, config_data):
        """
        Update the LLM configuration.
        
        Args:
            config_data: Dictionary with configuration settings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update the config with new values
            for key, value in config_data.items():
                self.config[key] = value
            
            # Save the updated config
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
                
            logger.info("LLM configuration updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating LLM configuration: {str(e)}", exc_info=True)
            return False