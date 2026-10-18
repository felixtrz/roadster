import { BoxGeometry, CylinderGeometry, Group, Mesh, MeshStandardMaterial, Quaternion, Vector3 } from '@iwsdk/core';

/**
 * The camera rig the Mounted view rides on, like the arm rigs used to film supercars: two carbon
 * rods in a V from suction mounts on the rear deck to a clamp just behind and below the lens. Car-local metres
 * (+X forward, +Y up, +Z right); shown only in the Mounted view.
 */
export const MOUNT_LENS = new Vector3(-4.6, 1.95, 0);

export function createMountRig(): Group {
  const rig = new Group();
  rig.name = 'MountRig';
  const carbon = new MeshStandardMaterial({ name: 'RigCarbon', color: 0x16181b, roughness: 0.38, metalness: 0.55 });
  const alloy = new MeshStandardMaterial({ name: 'RigAlloy', color: 0x6c7076, roughness: 0.32, metalness: 0.9 });
  const rubber = new MeshStandardMaterial({ name: 'RigRubber', color: 0x0a0a0b, roughness: 0.85 });
  // the clamp sits just behind and below the lens, so only the rods reach into the frame
  const clamp = new Vector3(MOUNT_LENS.x - 0.06, MOUNT_LENS.y - 0.17, 0);
  const up = new Vector3(0, 1, 0);
  const rod = (a: Vector3, b: Vector3, radius: number, material: MeshStandardMaterial): Mesh => {
    const length = a.distanceTo(b);
    const mesh = new Mesh(new CylinderGeometry(radius, radius, length, 12), material);
    mesh.position.copy(a).add(b).multiplyScalar(0.5);
    mesh.quaternion.copy(new Quaternion().setFromUnitVectors(up, b.clone().sub(a).normalize()));
    return mesh;
  };
  for (const side of [-1, 1]) {
    // suction cup on the rear deck, a short riser, then the long rod back to the clamp
    const foot = new Vector3(-1.95, 1.07, side * 0.34);
    const cup = new Mesh(new CylinderGeometry(0.075, 0.085, 0.03, 20), rubber);
    cup.position.copy(foot);
    rig.add(cup);
    const riserTop = foot.clone().add(new Vector3(-0.04, 0.09, 0));
    rig.add(rod(foot, riserTop, 0.018, alloy));
    rig.add(rod(riserTop, clamp, 0.016, carbon));
  }
  // a cross brace halfway and the clamp block
  rig.add(rod(new Vector3(-3.25, 1.47, -0.17), new Vector3(-3.25, 1.47, 0.17), 0.012, carbon));
  const block = new Mesh(new BoxGeometry(0.1, 0.06, 0.09), alloy);
  block.position.copy(clamp);
  rig.add(block);
  rig.visible = false;
  return rig;
}

export function disposeMountRig(rig: Group): void {
  const materials = new Set<MeshStandardMaterial>();
  rig.traverse((part) => {
    if (part instanceof Mesh) { part.geometry.dispose(); materials.add(part.material as MeshStandardMaterial); }
  });
  for (const material of materials) material.dispose();
}
