import re

class HL7Parser:
    @staticmethod
    def parse_message(message_str: str) -> dict:
        """
        Parses a standard pipe-delimited HL7 v2 message string.
        Returns a dictionary mapping segment names (e.g. MSH, PID, PV1) to a list of lists of components.
        """
        segments = {}
        # Normalize line endings
        lines = re.split(r'[\r\n]+', message_str.strip())
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('|')
            seg_name = parts[0]
            
            # MSH segment is special because the pipe itself is the first field delimiter
            if seg_name == 'MSH':
                # MSH-1 is '|', MSH-2 is encoding characters
                fields = ['|'] + parts[1:]
            else:
                fields = parts
                
            # Parse components split by '^'
            parsed_fields = []
            for field in fields:
                if '^' in field:
                    parsed_fields.append(field.split('^'))
                else:
                    parsed_fields.append(field)
            
            if seg_name not in segments:
                segments[seg_name] = []
            segments[seg_name].append(parsed_fields)
            
        return segments

    @staticmethod
    def get_field(parsed_msg: dict, path: str) -> str:
        """
        Extracts a field or component value using a path like 'PID-3.1' or 'PV1-19'.
        """
        try:
            match = re.match(r'^([A-Z0-9]{3})(?:-(\d+))?(?:\.(\d+))?$', path)
            if not match:
                return None
                
            seg_name, field_idx, comp_idx = match.groups()
            if seg_name not in parsed_msg:
                return None
                
            # Take the first segment instance for simplicity
            seg = parsed_msg[seg_name][0]
            
            # MSH offset handling
            if seg_name == 'MSH':
                if field_idx is None:
                    return seg
                idx = int(field_idx)
                # MSH-1 is at index 0, MSH-2 at index 1, etc.
                val = seg[idx - 1]
            else:
                if field_idx is None:
                    return seg
                idx = int(field_idx)
                val = seg[idx]
                
            if comp_idx is not None:
                c_idx = int(comp_idx)
                if isinstance(val, list):
                    return val[c_idx - 1]
                else:
                    return val if c_idx == 1 else None
            return val
        except Exception:
            return None

if __name__ == "__main__":
    test_msg = """MSH|^~\\&|ST_JUDE_EMR|ST_JUDE_GH|EMR_HUB|REGIONAL_HUB|202608152310||ADT^A08|MSG00001|P|2.4
PID|1||123456^^^STJ_MRN||DOE^JOHN^MIDDLE||19800101|M|||123 MAIN ST^^MEMPHIS^TN^38101
PV1|1|O|CLINIC_A|||||||||||||||STJ-998877"""
    
    parsed = HL7Parser.parse_message(test_msg)
    print("Parsed segments:", list(parsed.keys()))
    print("PID-3.1 (Patient ID):", HL7Parser.get_field(parsed, "PID-3.1"))
    print("PID-5.1 (Family Name):", HL7Parser.get_field(parsed, "PID-5.1"))
    print("PV1-19 (Visit Number):", HL7Parser.get_field(parsed, "PV1-19"))
