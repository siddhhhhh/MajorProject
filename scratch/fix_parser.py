with open('utils/report_parser.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacement1 = '''                # Extract and append structured tables via Camelot
                table_text = self._extract_tables_with_camelot(local_path)
                if table_text:
                    combined_text += table_text
                    
                if local_path != original_local_path:
                    try:
                        import os; os.remove(local_path)
                    except Exception:
                        pass
                return combined_text'''

replacement2 = '''                # Extract and append structured tables via Camelot
                table_text = self._extract_tables_with_camelot(local_path)
                if table_text:
                    combined_text += table_text
                    
                if local_path != original_local_path:
                    try:
                        import os; os.remove(local_path)
                    except Exception:
                        pass
                return combined_text
                
            except Exception as e:
                print(f"         ❌ pypdf extraction also failed: {e}")
                
                if local_path != original_local_path:
                    try:
                        import os; os.remove(local_path)
                    except Exception:
                        pass
                return ""
        
        print(f"         ❌ No PDF library available")
        
        if local_path != original_local_path:
            try:
                import os; os.remove(local_path)
            except Exception:
                pass
        return ""'''

# For the first match (pdfplumber)
target1 = '''                # Extract and append structured tables via Camelot
                table_text = self._extract_tables_with_camelot(local_path)
                if table_text:
                    combined_text += table_text
                return combined_text'''

# For the second match (pypdf)
target2 = '''                # Extract and append structured tables via Camelot
                table_text = self._extract_tables_with_camelot(local_path)
                if table_text:
                    combined_text += table_text
                return combined_text
                
            except Exception as e:
                print(f"         ❌ pypdf extraction also failed: {e}")
                return ""
        
        print(f"         ❌ No PDF library available")
        return ""'''

if target2 in content:
    content = content.replace(target2, replacement2)
    print('Target 2 replaced')
if target1 in content:
    content = content.replace(target1, replacement1)
    print('Target 1 replaced')

with open('utils/report_parser.py', 'w', encoding='utf-8') as f:
    f.write(content)
