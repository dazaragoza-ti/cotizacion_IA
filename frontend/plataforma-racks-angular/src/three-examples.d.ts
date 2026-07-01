declare module 'three/examples/jsm/loaders/GLTFLoader.js' {
  import { Loader } from 'three';
  import { LoadingManager, LoaderOptions, Group, AnimationClip } from 'three';

  export interface GLTF {
    scene: Group;
    scenes: Group[];
    animations: AnimationClip[];
    parser: any;
  }

  export class GLTFLoader extends Loader {
    constructor(manager?: LoadingManager);
    load(url: string, onLoad: (gltf: GLTF) => void, onProgress?: (event: ProgressEvent) => void, onError?: (event: ErrorEvent) => void): void;
    parse(data: ArrayBuffer, path: string, onLoad: (gltf: GLTF) => void, onError?: (event: ErrorEvent) => void): void;
    setDRACOLoader(dracoLoader: any): this;
  }
}

declare module 'three/examples/jsm/loaders/DRACOLoader.js' {
  import { Loader } from 'three';
  export class DRACOLoader extends Loader {
    constructor(manager?: any);
    setDecoderPath(path: string): this;
  }
}

declare module 'three/examples/jsm/exporters/GLTFExporter.js' {
  import { Object3D } from 'three';

  export class GLTFExporter {
    parse(
      input: Object3D,
      onCompleted: (data: ArrayBuffer | Blob | object) => void,
      onError?: (error: Error) => void,
      options?: any
    ): void;
  }
}
