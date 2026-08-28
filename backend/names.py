from __future__ import annotations

import random


MAN_NAMES = [
    "James", "Michael", "William", "David", "Daniel", "Robert", "John", "Thomas", "George", "Edward",
    "Liam", "Noah", "Oliver", "Ethan", "Lucas", "Henry", "Benjamin", "Jack", "Leo", "Arthur",
    "Mateo", "Santiago", "Diego", "Javier", "Alejandro", "Carlos", "Miguel", "Rafael", "Luis", "Andres",
    "Mohammed", "Omar", "Hassan", "Youssef", "Karim", "Samir", "Tariq", "Bilal", "Amir", "Nabil",
    "Wei", "Jun", "Ming", "Hao", "Chen", "Jin", "Tao", "Bo", "Liang", "Yong",
    "Hiroshi", "Kenji", "Daiki", "Haruto", "Ren", "Sota", "Yuki", "Takumi", "Riku", "Kaito",
    "Arjun", "Rohan", "Vikram", "Aarav", "Aditya", "Rahul", "Dev", "Kabir", "Ishaan", "Nikhil",
    "Thabo", "Sipho", "Kofi", "Kwame", "Tendai", "Musa", "Chinedu", "Emeka", "Bongani", "Jabari",
    "Anders", "Lars", "Soren", "Nikolai", "Mikhail", "Pavel", "Dmitri", "Ivan", "Marek", "Tomas",
    "Mateusz", "Jakub", "Felix", "Jonas", "Hugo", "Oscar", "Milan", "Luca", "Enzo", "Nico",
]

WOMAN_NAMES = [
    "Tina", "Sarah", "Emily", "Emma", "Olivia", "Sophia", "Grace", "Chloe", "Alice", "Evelyn",
    "Mia", "Ella", "Amelia", "Isla", "Ava", "Lily", "Sofia", "Freya", "Zoe", "Ruby",
    "Valentina", "Camila", "Lucia", "Mariana", "Isabella", "Gabriela", "Sofia", "Catalina", "Elena", "Ana",
    "Aisha", "Fatima", "Layla", "Zainab", "Mariam", "Noura", "Hana", "Salma", "Yasmin", "Leila",
    "Mei", "Xinyi", "Yue", "Lin", "Hui", "Xia", "Na", "Jia", "Lan", "Qiao",
    "Sakura", "Yui", "Aoi", "Hina", "Mio", "Rin", "Emi", "Nana", "Ayaka", "Miku",
    "Ananya", "Diya", "Priya", "Aditi", "Kavya", "Isha", "Meera", "Nisha", "Riya", "Sneha",
    "Ama", "Zuri", "Imani", "Nia", "Ayanda", "Lerato", "Amara", "Adesua", "Wanjiku", "Thandiwe",
    "Ingrid", "Astrid", "Freja", "Katarina", "Anastasia", "Olga", "Svetlana", "Mila", "Elena", "Petra",
    "Clara", "Anna", "Sofia", "Marta", "Nora", "Leonie", "Eva", "Lena", "Maja", "Alba",
]


def random_name(gender: str) -> str:
    return random.choice(MAN_NAMES if gender == "man" else WOMAN_NAMES)
