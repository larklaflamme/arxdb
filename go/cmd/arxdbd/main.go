// Command arxdbd is the ArxDB storage daemon.
//
// It opens a Pebble-backed storage engine and serves the StorageService gRPC
// API over a UNIX domain socket (local IPC). The Python verification layer
// talks to it through src/arxdb/storage/grpc_client.py, which presents the
// same Storage interface as the in-process SQLite backend.
//
// Usage:
//
//	arxdbd --data-dir /path/to/store [--socket /tmp/arxdb.sock] [--keypair /path/to/keypair.bin]
//
// The keypair is 64 bytes: a 32-byte Ed25519 private seed followed by the
// 32-byte public key (the same layout as the seed script's seed_keypair.bin).
// If --keypair is omitted, a fresh keypair is generated and persisted to
// <data-dir>/keypair.bin so the daemon's identity is stable across restarts.
package main

import (
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"

	"google.golang.org/grpc"

	"github.com/larklaflamme/arxdb/go/pkg/keys"
	"github.com/larklaflamme/arxdb/go/pkg/service"
	"github.com/larklaflamme/arxdb/go/pkg/storage"
	"github.com/larklaflamme/arxdb/go/proto/arxdbpb"
)

const keypairSize = 64 // 32-byte private seed + 32-byte public key

func main() {
	dataDir := flag.String("data-dir", "", "storage engine root (required)")
	socketPath := flag.String("socket", "/tmp/arxdb.sock", "UNIX socket path")
	keypairPath := flag.String("keypair", "", "path to a 64-byte keypair file (optional)")
	flag.Parse()

	if *dataDir == "" {
		log.Fatal("--data-dir is required")
	}
	if err := os.MkdirAll(*dataDir, 0o755); err != nil {
		log.Fatalf("create data dir: %v", err)
	}

	priv, pub, err := loadOrGenerateKeypair(*dataDir, *keypairPath)
	if err != nil {
		log.Fatalf("keypair: %v", err)
	}

	store, err := storage.Open(*dataDir, priv, pub)
	if err != nil {
		log.Fatalf("open storage: %v", err)
	}
	defer store.Close()

	// Remove a stale socket from a previous run.
	if err := os.RemoveAll(*socketPath); err != nil {
		log.Fatalf("remove stale socket: %v", err)
	}
	lis, err := net.Listen("unix", *socketPath)
	if err != nil {
		log.Fatalf("listen: %v", err)
	}

	srv := grpc.NewServer()
	arxdbpb.RegisterStorageServiceServer(srv, service.New(store))

	// Graceful shutdown on SIGINT/SIGTERM.
	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
		<-sig
		log.Println("shutting down")
		srv.GracefulStop()
	}()

	log.Printf("arxdbd serving on %s (data-dir %s)", *socketPath, *dataDir)
	if err := srv.Serve(lis); err != nil {
		log.Fatalf("serve: %v", err)
	}
}

// loadOrGenerateKeypair returns (priv, pub). If keypairPath is given, it is
// read (64 bytes). Otherwise a keypair is loaded from <dataDir>/keypair.bin,
// or generated and persisted there on first run.
func loadOrGenerateKeypair(dataDir, keypairPath string) ([]byte, []byte, error) {
	if keypairPath != "" {
		raw, err := os.ReadFile(keypairPath)
		if err != nil {
			return nil, nil, fmt.Errorf("read keypair: %w", err)
		}
		if len(raw) != keypairSize {
			return nil, nil, fmt.Errorf("keypair must be %d bytes, got %d", keypairSize, len(raw))
		}
		return raw[:32], raw[32:], nil
	}

	path := filepath.Join(dataDir, "keypair.bin")
	if raw, err := os.ReadFile(path); err == nil {
		if len(raw) != keypairSize {
			return nil, nil, fmt.Errorf("keypair must be %d bytes, got %d", keypairSize, len(raw))
		}
		return raw[:32], raw[32:], nil
	}

	priv, pub, err := keys.GenerateKeypair()
	if err != nil {
		return nil, nil, err
	}
	raw := append(append([]byte{}, priv...), pub...)
	if err := os.WriteFile(path, raw, 0o600); err != nil {
		return nil, nil, fmt.Errorf("persist keypair: %w", err)
	}
	log.Printf("generated new keypair at %s", path)
	return priv, pub, nil
}
