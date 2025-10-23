import api from "./client";
export async function listDepartments() {
  const { data } = await api.get("/departments"); // public per your backend change
  return data; // [{department_id,name,location}]
}
