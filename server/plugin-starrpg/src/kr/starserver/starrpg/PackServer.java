package kr.starserver.starrpg;

import com.sun.net.httpserver.HttpServer;

import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.concurrent.Executors;
import java.util.logging.Logger;

/** 리소스팩(zip)을 HTTP로 제공한다. 파일이 바뀌면 해시를 다시 계산한다. */
final class PackServer {
    private final File file;
    private final int port;
    private final Logger log;
    private HttpServer server;
    private long cachedModified = -1;
    private byte[] cachedBytes;
    private byte[] cachedSha1;

    private final File extra;    // 합칠 추가 리소스 폴더 (assets/...)
    private final File merged;   // 합친 결과 (팩업로드가 이 파일을 올린다)
    private long cachedExtra = -1;

    PackServer(File file, int port, Logger log) { this(file, null, null, port, log); }

    PackServer(File file, File extra, File merged, int port, Logger log) {
        this.file = file;
        this.extra = extra;
        this.merged = merged;
        this.port = port;
        this.log = log;
    }

    private static long newest(File f) {
        if (f == null || !f.exists()) return 0;
        long m = f.lastModified();
        File[] kids = f.listFiles();
        if (kids != null) for (File k : kids) m = Math.max(m, newest(k));
        return m;
    }

    /** 기본 팩 + 추가 폴더를 하나의 zip으로 (항목 시간 고정 → 같은 입력이면 같은 해시) */
    private byte[] merge(byte[] base) throws IOException {
        if (extra == null || !extra.isDirectory()) return base;
        java.util.TreeMap<String, byte[]> add = new java.util.TreeMap<>();
        java.nio.file.Path root = extra.toPath();
        try (var walk = Files.walk(root)) {
            for (var p : (Iterable<java.nio.file.Path>) walk.filter(Files::isRegularFile)::iterator)
                add.put(root.relativize(p).toString().replace(File.separatorChar, '/'), Files.readAllBytes(p));
        }
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream(base.length + 65536);
        try (var zin = new java.util.zip.ZipInputStream(new java.io.ByteArrayInputStream(base));
             var zout = new java.util.zip.ZipOutputStream(out)) {
            java.util.zip.ZipEntry e;
            while ((e = zin.getNextEntry()) != null) {
                if (add.containsKey(e.getName())) continue;
                java.util.zip.ZipEntry n = new java.util.zip.ZipEntry(e.getName());
                n.setTime(315532800000L);
                zout.putNextEntry(n);
                zin.transferTo(zout);
                zout.closeEntry();
            }
            for (var en : add.entrySet()) {
                java.util.zip.ZipEntry n = new java.util.zip.ZipEntry(en.getKey());
                n.setTime(315532800000L);
                zout.putNextEntry(n);
                zout.write(en.getValue());
                zout.closeEntry();
            }
        }
        return out.toByteArray();
    }

    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/pack.zip", ex -> {
            byte[] data = bytes();
            if (data == null) {
                ex.sendResponseHeaders(404, -1);
                ex.close();
                return;
            }
            ex.getResponseHeaders().add("Content-Type", "application/zip");
            ex.sendResponseHeaders(200, data.length);
            try (OutputStream os = ex.getResponseBody()) { os.write(data); }
        });
        server.setExecutor(Executors.newFixedThreadPool(2));
        server.start();
        log.info("리소스팩 서버 시작: 포트 " + port + " (" + file.getPath() + ")");
    }

    void stop() {
        if (server != null) server.stop(0);
    }

    int port() { return port; }

    synchronized byte[] bytes() {
        refresh();
        return cachedBytes;
    }

    synchronized byte[] sha1() {
        refresh();
        return cachedSha1;
    }

    private void refresh() {
        if (!file.isFile()) { cachedBytes = null; cachedSha1 = null; return; }
        long m = file.lastModified();
        long x = newest(extra);
        if (m == cachedModified && x == cachedExtra && cachedBytes != null) return;
        try {
            cachedBytes = merge(Files.readAllBytes(file.toPath()));
            cachedExtra = x;
            if (merged != null) Files.write(merged.toPath(), cachedBytes);
            cachedSha1 = MessageDigest.getInstance("SHA-1").digest(cachedBytes);
            cachedModified = m;
        } catch (Exception e) {
            log.warning("리소스팩 읽기 실패: " + e.getMessage());
            cachedBytes = null;
            cachedSha1 = null;
        }
    }
}
