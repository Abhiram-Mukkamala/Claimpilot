import React, { useMemo, useRef, useState, useEffect } from 'react';
import * as THREE from 'three';

interface DamageMeshProps {
  maxDeformationMm: number;
  imageUrl?: string;
}

export const DamageMesh: React.FC<DamageMeshProps> = ({ maxDeformationMm, imageUrl }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const [texture, setTexture] = useState<THREE.Texture | null>(null);
  
  useEffect(() => {
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin('Anonymous');
    loader.load(
      imageUrl || '/mock/car-damage.svg',
      (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        setTexture(tex);
      },
      undefined,
      (err) => {
        console.error('Failed to load texture for 3D mesh:', err);
      }
    );
  }, [imageUrl]);

  // Generate a procedural dented surface
  const { geometry, materials } = useMemo(() => {
    // 100x100 resolution plane
    const geom = new THREE.PlaneGeometry(10, 8, 100, 80);
    const pos = geom.attributes.position;
    
    // We'll also compute colors for the vertices based on Z depth
    const colors = new Float32Array(pos.count * 3);
    
    // Mock dent parameters: center (2, -1), radius 2.5
    const cx = 2;
    const cy = -1;
    const radius = 2.5;
    
    let maxZ = 0;
    
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      
      const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
      
      let z = 0;
      if (dist < radius) {
        // Gaussian-like dent
        // Normalized depth 0 to 1
        const depth = Math.exp(-(dist ** 2) / (radius * 0.5));
        // Scale to maxDeformationMm (for visualization, we'll scale it to visual units)
        // A visual scale factor, e.g., max 1.5 units deep in 3D space
        z = -depth * 1.5; 
      }
      
      pos.setZ(i, z);
      maxZ = Math.min(maxZ, z); // z is negative
    }
    
    // Calculate colors (Heatmap: flat=white, deep=red)
    // We use white instead of silver so the texture map shows through properly
    for (let i = 0; i < pos.count; i++) {
      const z = pos.getZ(i);
      // normalized depth 0 (flat) to 1 (deepest)
      const normalizedDepth = maxZ === 0 ? 0 : z / maxZ; 
      
      // Color gradient for the heatmap overlay
      const color = new THREE.Color();
      if (normalizedDepth < 0.25) {
        color.setHSL(0.6, 0.8, 0.5 + normalizedDepth); // Blue to lighter blue
      } else if (normalizedDepth < 0.5) {
        color.setHSL(0.5 - (normalizedDepth - 0.25), 0.8, 0.5); // Cyan to Green
      } else if (normalizedDepth < 0.75) {
        color.setHSL(0.3 - (normalizedDepth - 0.5), 0.8, 0.5); // Green to Yellow
      } else {
        color.setHSL(0.1 - (normalizedDepth - 0.75) * 0.4, 0.8, 0.5); // Yellow to Red
      }
      
      // Mix with white (so texture is fully visible where there's no dent)
      const baseColor = new THREE.Color(0xffffff);
      // We only apply the heatmap color strongly where the dent is deep
      const mixRatio = normalizedDepth * 0.7; 
      baseColor.lerp(color, mixRatio);
      
      colors[i * 3] = baseColor.r;
      colors[i * 3 + 1] = baseColor.g;
      colors[i * 3 + 2] = baseColor.b;
    }
    
    geom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geom.computeVertexNormals();

    const mat = new THREE.MeshStandardMaterial({
      map: texture,
      vertexColors: true,
      roughness: 0.6,
      metalness: 0.2,
      side: THREE.DoubleSide
    });
    
    // Wireframe material for toggle if needed
    const wireMat = new THREE.MeshBasicMaterial({
      color: 0x000000,
      wireframe: true,
      transparent: true,
      opacity: 0.1
    });

    return { geometry: geom, materials: [mat, wireMat] };
  }, [maxDeformationMm, texture]);

  return (
    <group>
      <mesh ref={meshRef} geometry={geometry} material={materials[0]} />
      {/* Optional subtle wireframe overlay */}
      <mesh geometry={geometry} material={materials[1]} position={[0, 0, 0.01]} />
    </group>
  );
};
