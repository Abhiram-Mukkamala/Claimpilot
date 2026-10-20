/**
 * Agent Evidence Mapping and Normalization Tests.
 *
 * Runs on Node's built-in test runner:
 *   npm test
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { mapBackendClaimToFrontend } from '../src/services/claimsApi.ts';

describe('mapBackendClaimToFrontend — Evidence Normalization', () => {
  test('maps full backend evidence list into claim.evidence items', () => {
    const rawClaim = {
      id: 'claim-101',
      claim_number: 'CLM-2026-88888',
      user_id: 'user-001',
      status: 'pending_review',
      vehicle_name: '2024 Honda Civic',
      driver_name: 'John Doe',
      policy_number: 'POL-12345',
      created_at: '2026-10-19T10:00:00Z',
    };

    const evidenceList = [
      {
        id: 'ev-1',
        claim_id: 'claim-101',
        category: 'damage_photo',
        file_url: 'https://storage.supabase.co/damage1.jpg',
        file_type: 'image/jpeg',
        created_at: '2026-10-19T10:05:00Z',
      },
      {
        id: 'ev-2',
        claim_id: 'claim-101',
        category: 'walkaround_video',
        file_url: 'https://storage.supabase.co/walkaround.mp4',
        file_type: 'video/mp4',
        created_at: '2026-10-19T10:06:00Z',
      },
      {
        id: 'ev-3',
        claim_id: 'claim-101',
        category: 'dl_front',
        file_url: 'https://storage.supabase.co/dl_front.jpg',
        file_type: 'image/jpeg',
        created_at: '2026-10-19T10:07:00Z',
      },
      {
        id: 'ev-4',
        claim_id: 'claim-101',
        category: 'dl_back',
        file_url: 'https://storage.supabase.co/dl_back.jpg',
        file_type: 'image/jpeg',
        created_at: '2026-10-19T10:08:00Z',
      },
    ];

    const mapped = mapBackendClaimToFrontend(rawClaim, evidenceList);

    assert.ok(mapped.evidence, 'evidence array should exist');
    assert.equal(mapped.evidence.length, 4);

    // Photos
    assert.equal(mapped.images.length, 1);
    assert.equal(mapped.images[0], 'https://storage.supabase.co/damage1.jpg');

    // Video
    assert.equal(mapped.video, 'https://storage.supabase.co/walkaround.mp4');
    assert.equal(mapped.videos?.length, 1);

    // Driver License
    assert.equal(mapped.driverLicenseFrontPhoto, 'https://storage.supabase.co/dl_front.jpg');
    assert.equal(mapped.driverLicenseBackPhoto, 'https://storage.supabase.co/dl_back.jpg');

    // Check evidence item details
    const videoItem = mapped.evidence.find((e) => e.category === 'walkaround_video');
    assert.ok(videoItem, 'Walkaround video should be present in evidence list');
    assert.equal(videoItem.file_url, 'https://storage.supabase.co/walkaround.mp4');
    assert.equal(videoItem.file_type, 'video/mp4');

    const dlFrontItem = mapped.evidence.find((e) => e.category === 'dl_front');
    assert.ok(dlFrontItem, 'DL front should be present in evidence list');
  });

  test('synthesizes evidence items when only raw fallback fields exist', () => {
    const rawClaim = {
      id: 'claim-102',
      claim_number: 'CLM-2026-99999',
      images: ['https://storage.supabase.co/raw-photo1.jpg', 'https://storage.supabase.co/raw-photo2.jpg'],
      video: 'https://storage.supabase.co/raw-video.mp4',
      driverLicenseFrontPhoto: 'https://storage.supabase.co/raw-dl-front.jpg',
      driverLicenseBackPhoto: 'https://storage.supabase.co/raw-dl-back.jpg',
    };

    const mapped = mapBackendClaimToFrontend(rawClaim, []);

    assert.ok(mapped.evidence, 'evidence array should be created');
    assert.equal(mapped.evidence.length, 5); // 2 photos, 1 video, 2 DLs

    const categories = mapped.evidence.map((e) => e.category);
    assert.ok(categories.includes('dl_front'));
    assert.ok(categories.includes('dl_back'));
    assert.ok(categories.includes('walkaround_video'));
    assert.ok(categories.includes('damage_photo'));
  });

  test('deduplicates URLs between evidenceList and raw fallback fields', () => {
    const rawClaim = {
      id: 'claim-103',
      claim_number: 'CLM-2026-11111',
      images: ['https://storage.supabase.co/shared-photo.jpg'],
      driverLicenseFrontPhoto: 'https://storage.supabase.co/shared-dl-front.jpg',
    };

    const evidenceList = [
      {
        id: 'ev-unique-1',
        category: 'photo',
        file_url: 'https://storage.supabase.co/shared-photo.jpg',
      },
      {
        id: 'ev-unique-2',
        category: 'dl_front',
        file_url: 'https://storage.supabase.co/shared-dl-front.jpg',
      },
    ];

    const mapped = mapBackendClaimToFrontend(rawClaim, evidenceList);

    assert.equal(mapped.evidence?.length, 2, 'Duplicates should not be appended');
  });
});
