export interface CurrentUser {
  id: number;
  name: string;
  email: string;
  role: string;
  clinic: {
    id: number;
    name: string;
  };
}
