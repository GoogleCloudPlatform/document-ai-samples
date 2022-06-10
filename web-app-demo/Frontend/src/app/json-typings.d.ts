declare module "*.json" {
  const value: any;
  export default value;
}

interface IProcessor {
  name: string;
  type: string;
  displayName: string;
}
