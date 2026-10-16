import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { DamageMesh } from './DamageMesh';

interface DamageSceneProps {
  maxDeformationMm: number;
  imageUrl?: string;
}

export const DamageScene: React.FC<DamageSceneProps> = ({ maxDeformationMm, imageUrl }) => {
  return (
    <div className="w-full h-full cursor-move bg-black rounded-md overflow-hidden">
      <Canvas 
        shadows 
        camera={{ position: [0, -6, 6], fov: 45 }}
        gl={{ antialias: true, alpha: false }}
      >
        <color attach="background" args={['#1a1c23']} />
        
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 10]} intensity={1} castShadow />
        <directionalLight position={[-10, -10, 5]} intensity={0.5} color="#4a5568" />
        
        <Suspense fallback={null}>
          <DamageMesh maxDeformationMm={maxDeformationMm} imageUrl={imageUrl} />
        </Suspense>
        
        <OrbitControls 
          makeDefault
          enableDamping 
          dampingFactor={0.05} 
          minDistance={2} 
          maxDistance={20}
          maxPolarAngle={Math.PI / 2} // don't go below ground
        />
      </Canvas>
    </div>
  );
};
