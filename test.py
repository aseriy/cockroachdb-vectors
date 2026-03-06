import re
import json

sql = """
CREATE OR REPLACE FUNCTION clear_vector_on_source_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF (NEW).passage <> (OLD).passage THEN
        NEW.passage_vector := NULL;
        NEW.passage_openai := NULL;
    END IF;

    IF (NEW).description <> (OLD).description THEN
        NEW.description_hf := NULL;
        NEW.description_openai := NULL;
    END IF;

    RETURN NEW;
END;
$$;
"""

config = []

# 1. Extract everything between $$ ... $$
body_match = re.search(r'\$\$(.*?)\$\$', sql, re.DOTALL)
if body_match:
    body = body_match.group(1)
    
    # 2. Find each IF ... END IF block
    # This captures the condition and the internal assignments
    blocks = re.findall(r'IF\s+(.*?)\s+THEN(.*?)\s+END IF;', body, re.DOTALL)
    
    for condition, assignments in blocks:
        # Extract the input column from (NEW).colname
        # Match handles both "(NEW).col" and "NEW.col"
        input_col = re.search(r'\(?NEW\)?\.(\w+)', condition)
        
        # Extract all output columns from "NEW.colname := NULL"
        output_cols = re.findall(r'NEW\.(\w+)\s*:=', assignments)
        
        if input_col and output_cols:
            config.append({
                'input': input_col.group(1),
                'output': output_cols
            })


print(json.dumps(config, indent=2))
