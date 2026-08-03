import { postApi } from './http'

export function updatePassword(body: {
  userName: string
  password: string
  newPassword: string
}) {
  return postApi('/v2/vectordb/users/update_password', body)
}
