/**
 * Hook for managing one-time-use image access tokens.
 *
 * Security Model:
 * - Tokens are one-time-use (consumed on first image load)
 * - Tokens are tenant-scoped (server validates tenant ownership)
 * - Tokens expire after ~90 seconds
 * - Frontend auto-refreshes tokens before expiry
 *
 * Usage:
 * const { tokenUrls, isLoading, error, refreshTokens } = useImageTokens(images);
 * <img src={resolveImageUrl(tokenUrls['image-id'])} />
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { imageApi, resolveImageUrl } from '../services/api';
import { CheckImage } from '../types';

// Refresh tokens 30 seconds before expiry (tokens have 90s TTL)
const TOKEN_REFRESH_BUFFER_MS = 30 * 1000;

// Minimum interval between refresh attempts (prevent rapid retries)
const MIN_REFRESH_INTERVAL_MS = 5 * 1000;

interface TokenInfo {
  tokenId: string;
  imageUrl: string;
  expiresAt: Date;
}

interface UseImageTokensResult {
  /** Map of image ID to secure URL */
  tokenUrls: Record<string, string>;
  /** Whether tokens are being loaded */
  isLoading: boolean;
  /** Error if token minting failed */
  error: Error | null;
  /** Manually trigger token refresh */
  refreshTokens: () => Promise<void>;
  /** Refresh token for a single image (e.g., on load error) */
  refreshImageToken: (imageId: string) => Promise<string | null>;
}

export function useImageTokens(
  images: CheckImage[],
  options: { isThumbnail?: boolean } = {}
): UseImageTokensResult {
  const { isThumbnail = false } = options;

  const [tokens, setTokens] = useState<Record<string, TokenInfo>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Track last refresh time to prevent rapid retries
  const lastRefreshRef = useRef<number>(0);
  // Track refresh timer
  const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
  // Track mounted state
  const mountedRef = useRef(true);

  // Get image IDs that need tokens
  const imageIds = images.map((img) => img.id).filter(Boolean);

  // Mint tokens for all images
  const mintTokens = useCallback(async (ids: string[]) => {
    if (ids.length === 0) return;

    // Rate limit refreshes
    const now = Date.now();
    if (now - lastRefreshRef.current < MIN_REFRESH_INTERVAL_MS) {
      return;
    }
    lastRefreshRef.current = now;

    setIsLoading(true);
    setError(null);

    try {
      const response = await imageApi.mintTokensBatch(ids, isThumbnail);

      if (!mountedRef.current) return;

      // Build token map
      const newTokens: Record<string, TokenInfo> = {};
      let earliestExpiry: Date | null = null;

      response.tokens.forEach((token, index) => {
        const imageId = ids[index];
        if (imageId) {
          const expiresAt = new Date(token.expires_at);
          newTokens[imageId] = {
            tokenId: token.token_id,
            imageUrl: token.image_url,
            expiresAt,
          };

          if (!earliestExpiry || expiresAt < earliestExpiry) {
            earliestExpiry = expiresAt;
          }
        }
      });

      setTokens(newTokens);

      // Schedule refresh before earliest token expires
      if (earliestExpiry && refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }

      if (earliestExpiry) {
        const refreshIn = Math.max(
          earliestExpiry.getTime() - Date.now() - TOKEN_REFRESH_BUFFER_MS,
          MIN_REFRESH_INTERVAL_MS
        );

        refreshTimerRef.current = setTimeout(() => {
          if (mountedRef.current) {
            mintTokens(ids);
          }
        }, refreshIn);
      }
    } catch (err) {
      if (!mountedRef.current) return;
      console.error('Failed to mint image tokens:', err);
      setError(err instanceof Error ? err : new Error('Failed to load image tokens'));
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [isThumbnail]);

  // Refresh token for a single image (e.g., on image load error)
  const refreshImageToken = useCallback(async (imageId: string): Promise<string | null> => {
    try {
      const response = await imageApi.mintToken(imageId, isThumbnail);

      if (!mountedRef.current) return null;

      setTokens((prev) => ({
        ...prev,
        [imageId]: {
          tokenId: response.token_id,
          imageUrl: response.image_url,
          expiresAt: new Date(response.expires_at),
        },
      }));

      return response.image_url;
    } catch (err) {
      console.error('Failed to refresh image token:', err);
      return null;
    }
  }, [isThumbnail]);

  // Initial token minting when images change
  useEffect(() => {
    if (imageIds.length > 0) {
      mintTokens(imageIds);
    }

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, [imageIds.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  // Build URL map from tokens
  const tokenUrls: Record<string, string> = {};
  for (const [imageId, token] of Object.entries(tokens)) {
    tokenUrls[imageId] = token.imageUrl;
  }

  return {
    tokenUrls,
    isLoading,
    error,
    refreshTokens: () => mintTokens(imageIds),
    refreshImageToken,
  };
}

export default useImageTokens;
