import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { MeetingFormDialog } from "@/components/MeetingFormDialog"
import { mockFetch, renderWithQuery } from "@/test/utils"

const START = new Date(2026, 8, 28, 10)

function renderForm() {
  const fetchMock = mockFetch(() => ({ body: [] }))
  renderWithQuery(<MeetingFormDialog open onOpenChange={() => {}} initialStart={START} />)
  return fetchMock
}

describe("MeetingFormDialog", () => {
  it("requires a title and a call link or place", async () => {
    const fetchMock = renderForm()
    await userEvent.click(screen.getByRole("button", { name: "Create meeting" }))

    expect(await screen.findByText("Title is required")).toBeInTheDocument()
    expect(screen.getByText("Provide a call link, a place, or both")).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalledWith(
      "/api/meetings",
      expect.objectContaining({ method: "POST" }),
    )
  })

  it("rejects a malformed call link", async () => {
    renderForm()
    await userEvent.type(screen.getByLabelText("Title"), "Standup")
    await userEvent.type(screen.getByLabelText("Call link"), "not a url")
    await userEvent.click(screen.getByRole("button", { name: "Create meeting" }))

    expect(await screen.findByText("Enter a valid http(s) URL")).toBeInTheDocument()
  })

  it("requires the meeting to end after it starts", async () => {
    renderForm()
    await userEvent.type(screen.getByLabelText("Title"), "Standup")
    await userEvent.type(screen.getByLabelText("Place"), "Room 1")
    await userEvent.clear(screen.getByLabelText("End"))
    await userEvent.type(screen.getByLabelText("End"), "09:30")
    await userEvent.click(screen.getByRole("button", { name: "Create meeting" }))

    expect(await screen.findByText("End must be after start")).toBeInTheDocument()
  })

  it("submits valid data to the API", async () => {
    const fetchMock = renderForm()
    await userEvent.type(screen.getByLabelText("Title"), "Standup")
    await userEvent.type(screen.getByLabelText("Place"), "Room 1")
    await userEvent.click(screen.getByRole("button", { name: "Create meeting" }))

    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")
    expect(post?.[0]).toBe("/api/meetings")
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      title: "Standup",
      description: null,
      call_link: null,
      place: "Room 1",
      starts_at: START.toISOString(),
      ends_at: new Date(2026, 8, 28, 11).toISOString(),
      participant_ids: [],
    })
  })
})
