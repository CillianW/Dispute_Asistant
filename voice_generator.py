def generate_twiml(script):
    """生成 TwiML 语音脚本"""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="en-US">
        {script}
    </Say>
    <Pause length="2"/>
    <Say voice="alice" language="en-US">
        Thank you for listening. Goodbye.
    </Say>
</Response>
"""
    return twiml 