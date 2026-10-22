package main

import (
	"io"
	"testing"
)

// The Buffer cursor must not expose a method named ReadByte.
//
// A `ReadByte() byte` method collides with io.ByteReader's required
// `ReadByte() (byte, error)` signature: go vet reports
// "method ReadByte() byte should have signature ReadByte() (byte, error)",
// and any code path that hands a *Buffer to something expecting io.ByteReader
// (bufio, encoding/binary helpers, zlib readers) would either fail to compile
// or silently take the wrong branch. The cursor cannot report EOF, so the
// correctly named accessor is NextByte.
func TestBufferDoesNotClaimIOByteReader(t *testing.T) {
	var bb any = NewBufferFrom([]byte{1, 2, 3})

	if _, ok := bb.(io.ByteReader); ok {
		t.Fatal("Buffer implements io.ByteReader, but its cursor cannot report EOF; rename the method")
	}
}

func TestBufferNextByteAdvances(t *testing.T) {
	bb := NewBufferFrom([]byte{0xAA, 0xBB, 0xCC})

	if got, want := bb.NextByte(), byte(0xAA); got != want {
		t.Fatalf("NextByte() #1 = %#x, want %#x", got, want)
	}
	if got, want := bb.NextByte(), byte(0xBB); got != want {
		t.Fatalf("NextByte() #2 = %#x, want %#x", got, want)
	}
	if got, want := bb.offset, 2; got != want {
		t.Fatalf("offset after two reads = %d, want %d", got, want)
	}
}

func TestBufferNextBytePastEndReturnsZero(t *testing.T) {
	bb := NewBufferFrom([]byte{0x01})
	bb.NextByte()

	// Overrun yields the zero byte rather than panicking.
	if got, want := bb.NextByte(), byte(0); got != want {
		t.Fatalf("NextByte() past end = %#x, want %#x", got, want)
	}
}

func TestBufferReadIntAndResetOffset(t *testing.T) {
	bb := NewBufferFrom([]byte{0x00, 0x00, 0x01, 0x00, 0x09})

	if got, want := bb.ReadInt(), 256; got != want {
		t.Fatalf("ReadInt() #1 = %d, want %d", got, want)
	}
	bb.ResetOffset()
	if got, want := bb.ReadInt(), 256; got != want {
		t.Fatalf("ReadInt() after ResetOffset() = %d, want %d", got, want)
	}
}

func TestBufferReadIntOnShortInput(t *testing.T) {
	bb := NewBufferFrom(nil)
	if got, want := bb.ReadInt(), 0; got != want {
		t.Fatalf("ReadInt() on empty = %d, want %d", got, want)
	}
}
