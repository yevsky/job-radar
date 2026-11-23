"""Conversations: create, list, read, rename, delete; nobody sees another user's chats."""

from fastapi import status
from fastapi.testclient import TestClient

from tests.chat.conftest import Headers, Script, say, send


def test_a_new_conversation_has_no_title(api: TestClient, chat_id: int, headers: Headers) -> None:
    body = api.get(f'/chat/{chat_id}', headers=headers).json()
    assert body['title'] is None
    assert body['messages'] == []
    assert body['actions'] == []


def test_the_first_message_becomes_the_title(
    api: TestClient, chat_id: int, headers: Headers, script: Script
) -> None:
    script(say('Hi!'))
    send(api, headers, chat_id, 'x' * 100)
    send(api, headers, chat_id, 'Second message')
    body = api.get(f'/chat/{chat_id}', headers=headers).json()
    assert body['title'] == 'x' * 80


def test_list_is_newest_first(
    api: TestClient, headers: Headers, chat_id: int, script: Script
) -> None:
    second = api.post('/chat', headers=headers).json()['id']
    script(say('Hi!'))
    send(api, headers, chat_id, 'Hello')  # the older one is now the last active
    ids = [row['id'] for row in api.get('/chat', headers=headers).json()]
    assert ids == [chat_id, second]


def test_rename(api: TestClient, headers: Headers, chat_id: int) -> None:
    response = api.patch(f'/chat/{chat_id}', json={'title': '  Python jobs  '}, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['title'] == 'Python jobs'
    assert api.get(f'/chat/{chat_id}', headers=headers).json()['title'] == 'Python jobs'


def test_a_rename_keeps_the_chats_place_in_the_list(
    api: TestClient, headers: Headers, chat_id: int
) -> None:
    newer = api.post('/chat', headers=headers).json()['id']
    api.patch(f'/chat/{chat_id}', json={'title': 'Renamed'}, headers=headers)
    ids = [row['id'] for row in api.get('/chat', headers=headers).json()]
    assert ids == [newer, chat_id]


def test_a_renamed_chat_keeps_its_name_after_the_next_message(
    api: TestClient, headers: Headers, chat_id: int, script: Script
) -> None:
    api.patch(f'/chat/{chat_id}', json={'title': 'My name'}, headers=headers)
    script(say('Hi!'))
    send(api, headers, chat_id, 'Hello')
    assert api.get(f'/chat/{chat_id}', headers=headers).json()['title'] == 'My name'


def test_a_title_must_have_text_and_fit(api: TestClient, headers: Headers, chat_id: int) -> None:
    for title in ['', '   ', 'x' * 81]:
        response = api.patch(f'/chat/{chat_id}', json={'title': title}, headers=headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_delete(api: TestClient, headers: Headers, chat_id: int) -> None:
    response = api.delete(f'/chat/{chat_id}', headers=headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert api.get(f'/chat/{chat_id}', headers=headers).status_code == status.HTTP_404_NOT_FOUND


def test_another_users_conversation_is_404(
    api: TestClient, chat_id: int, other_headers: Headers
) -> None:
    assert api.get('/chat', headers=other_headers).json() == []
    for response in [
        api.get(f'/chat/{chat_id}', headers=other_headers),
        api.delete(f'/chat/{chat_id}', headers=other_headers),
        api.patch(f'/chat/{chat_id}', json={'title': 'Mine'}, headers=other_headers),
        api.post(f'/chat/{chat_id}/messages', json={'content': 'Hi'}, headers=other_headers),
        api.post(f'/chat/{chat_id}/actions/1/confirm', headers=other_headers),
        api.post(f'/chat/{chat_id}/actions/1/cancel', headers=other_headers),
    ]:
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_needs_login(api: TestClient) -> None:
    assert api.get('/chat').status_code == status.HTTP_401_UNAUTHORIZED
