import { describe, expect, it } from "vitest";
import { redactSensitive } from "../src/util/redact.js";

describe("redactSensitive", () => {
  it("scrubs Bearer tokens", () => {
    const input = `{"headers":"Authorization: Bearer sk-ABCDEFG123456789xyz"}`;
    expect(redactSensitive(input)).not.toContain("sk-ABCDEFG123456789xyz");
    expect(redactSensitive(input)).toContain("Bearer <redacted>");
  });

  it("scrubs sk-* style keys embedded in text", () => {
    const out = redactSensitive("hi sk-abcdefghij1234567890 there");
    expect(out).toBe("hi sk-<redacted> there");
  });

  it("scrubs sk-ant-* anthropic keys before sk-* generic", () => {
    const out = redactSensitive("key=sk-ant-abc1234567890XYZ end");
    expect(out).toContain("sk-ant-<redacted>");
    expect(out).not.toContain("abc1234567890XYZ");
  });

  it("replaces JSON credential field values without breaking JSON shape", () => {
    const json = `{"api_key":"verysecret123456","other":"keep"}`;
    const out = redactSensitive(json);
    const parsed = JSON.parse(out);
    expect(parsed.api_key).toBe("<redacted>");
    expect(parsed.other).toBe("keep");
  });

  it("handles authorization, access_token, password fields", () => {
    const json = `{"authorization":"foo","access_token":"bar","password":"pw"}`;
    const out = redactSensitive(json);
    const parsed = JSON.parse(out);
    expect(parsed.authorization).toBe("<redacted>");
    expect(parsed.access_token).toBe("<redacted>");
    expect(parsed.password).toBe("<redacted>");
  });

  it("leaves non-sensitive content untouched", () => {
    const text = `{"messages":[{"role":"user","content":"hello world"}]}`;
    expect(redactSensitive(text)).toBe(text);
  });

  it("returns empty input as-is", () => {
    expect(redactSensitive("")).toBe("");
  });
});
