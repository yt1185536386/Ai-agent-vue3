package com.v3agent.rag.auth;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;

/**
 * JWT 校验（只校验不签发）。
 * 与 model-gateway / NestJS 共享 JWT_SECRET，claims 对齐 sub / username。
 */
@Component
public class JwtUtil {

    private final SecretKey key;

    public JwtUtil(@Value("${rag.jwt.secret}") String secret) {
        String s = secret.length() >= 32 ? secret : (secret + secret + secret + secret).substring(0, 32);
        this.key = Keys.hmacShaKeyFor(s.getBytes(StandardCharsets.UTF_8));
    }

    /** 校验失败返回 null */
    public Claims parse(String token) {
        try {
            return Jwts.parser().verifyWith(key).build()
                    .parseSignedClaims(token).getPayload();
        } catch (JwtException | IllegalArgumentException e) {
            return null;
        }
    }
}
